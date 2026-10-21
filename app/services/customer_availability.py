"""Customer "I'm home now" for a Collect Later household stop.

When a driver marks a household stop Collect Later, the customer is told the
waste will be collected later today. If they are home, the citizen app lets
them say so: `mark_customer_available()` stamps `customer_available_at` on
today's stop and alerts the trip crew. The driver resolves it with the
actions they already have (collect, or mark Not Available) — there is no
separate request workflow.

If a stop the customer flagged still ends Not Available — by the driver or the
Re-Trip flow — `raise_missed_pickup_ticket()` opens a MISSED_PICKUP complaint
ticket for the customer, so the miss is on record and goes through the
normal ticket routing, SLA and escalation (app/utils/complaint_ticket_routing).
"""

import logging

from django.db import transaction
from django.utils import timezone

from app.models.core_modules.complaint_management import (
    ComplaintCategory,
    ComplaintSource,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintSubcategory,
    ComplaintTicket,
    ComplaintTicketExtraDetail,
)
from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.notifications.staff_notification import StaffNotification

logger = logging.getLogger(__name__)

SYSTEM_SOURCE_CODE = "SYSTEM"
MISSED_PICKUP_CODE = "MISSED_PICKUP"
NOT_COLLECTED_SUBCATEGORY_CODE = "NOT_COLLECTED"
INCIDENT_TYPE = "Missed pickup - customer was available"

# The customer's flat geography copied onto the ticket.
_TICKET_GEO_FIELDS = (
    "state_id",
    "district_id",
    "area_type_id",
    "corporation_id",
    "municipality_id",
    "town_panchayat_id",
    "panchayat_union_id",
    "panchayat_id",
)


class AvailabilityError(Exception):
    """Raised with a citizen-readable message when the stop can't be flagged."""


def todays_stop(customer):
    """The customer's household stop on today's trip, or None.

    A Re-Trip leaves the original row behind (with `carried_to_assignment_id`
    set) and creates a new one on the continuation, so prefer the row that
    was not carried away.
    """
    today_ids = DailyTripAssignment.objects.filter(
        trip_date=timezone.localdate(), is_deleted=False,
    ).values_list("unique_id", flat=True)
    stops = list(
        DailyTripHouseholdCollection.objects.filter(
            customer_id=customer.unique_id,
            trip_assignment_id__in=list(today_ids),
            is_deleted=False,
        ).order_by("-created_at")
    )
    if not stops:
        return None
    live = [s for s in stops if not s.carried_to_assignment_id]
    return (live or stops)[0]


def _crew_of(assignment):
    from app.services.retrip_service import _crew_of as retrip_crew

    return retrip_crew(assignment)


@transaction.atomic
def mark_customer_available(customer, note=None):
    stop = todays_stop(customer)
    if stop is None:
        raise AvailabilityError("There is no collection scheduled for you today.")
    stop = DailyTripHouseholdCollection.objects.select_for_update().get(pk=stop.pk)
    if stop.status != DailyTripHouseholdCollection.STATUS_COLLECT_LATER:
        raise AvailabilityError(
            "You can only do this when your pickup is marked Collect Later."
        )
    assignment = DailyTripAssignment.objects.filter(
        unique_id=stop.trip_assignment_id
    ).first()
    if assignment is None or assignment.status != DailyTripAssignment.STATUS_IN_PROGRESS:
        raise AvailabilityError("Today's collection trip has already ended.")
    if stop.customer_available_at:
        # One alert per stop: a second tap must not spam the crew.
        return stop, False

    stop.customer_available_at = timezone.now()
    stop.customer_available_note = (str(note or "").strip()[:200]) or None
    stop.save(update_fields=["customer_available_at", "customer_available_note", "updated_at"])

    transaction.on_commit(lambda: _alert_crew(stop, assignment, customer))
    return stop, True


def _alert_crew(stop, assignment, customer):
    from app.services.staff_notification_service import notify_staff

    name = getattr(customer, "customer_name", None) or "A customer"
    body = f"{name} is home now. Please collect their waste on this trip."
    if stop.customer_available_note:
        body += f' Note: "{stop.customer_available_note}"'
    for staff in _crew_of(assignment):
        try:
            notify_staff(
                staff,
                StaffNotification.TYPE_CUSTOMER_AVAILABLE,
                "Customer available now",
                body,
                data={
                    "event": "customer_available",
                    "assignment_id": assignment.unique_id,
                    "household_stop_id": stop.unique_id,
                    "customer_id": stop.customer_id,
                },
            )
        except Exception:
            logger.exception("Could not alert %s for stop %s", staff, stop.unique_id)


def _idempotency_key(stop):
    return f"auto-missed-pickup:{stop.unique_id}"


def missed_pickup_ticket(stop):
    return ComplaintTicket.objects.filter(
        idempotency_key=_idempotency_key(stop), is_deleted=False
    ).first()


def raise_missed_pickup_ticket(stop):
    """Open a Missed Pickup ticket for a flagged stop that ended Not Available.

    Idempotent (keyed on the stop) and never raises — a ticket failure must
    not break the driver action that triggered it.
    """
    try:
        if (
            not stop.customer_available_at
            or stop.status != DailyTripHouseholdCollection.STATUS_MISSED
        ):
            return None
        existing = missed_pickup_ticket(stop)
        if existing:
            return existing
        with transaction.atomic():
            return _create_ticket(stop)
    except Exception:
        logger.exception("Could not raise missed pickup ticket for %s", stop.unique_id)
        return None


def _create_ticket(stop):
    from app.utils.complaint_ticket_routing import apply_routing_and_sla

    customer = stop.customer
    if customer is None:
        return None
    category = ComplaintCategory.objects.filter(
        category_code=MISSED_PICKUP_CODE, is_deleted=False
    ).first()
    status_obj = ComplaintStatus.objects.filter(
        status_code="SUBMITTED", is_deleted=False
    ).first()
    priority = getattr(category, "default_priority", None)
    if not category or not status_obj or not priority:
        logger.warning(
            "Missed pickup ticket skipped for %s: complaint masters not configured",
            stop.unique_id,
        )
        return None
    subcategory = ComplaintSubcategory.objects.filter(
        category_id=category.unique_id,
        subcategory_code=NOT_COLLECTED_SUBCATEGORY_CODE,
        is_deleted=False,
    ).first()
    source, _ = ComplaintSource.objects.get_or_create(
        source_code=SYSTEM_SOURCE_CODE,
        defaults={"source_name": "System (automatic)"},
    )

    available_at = timezone.localtime(stop.customer_available_at).strftime("%d %b %Y, %H:%M")
    description = (
        f"Automatic complaint: the customer reported being home at {available_at} "
        f"after the pickup was marked Collect Later, but the stop ended Not Available "
        f"(trip {stop.trip_assignment_id})."
    )
    if stop.status_reason:
        description += f" Reason recorded: {stop.status_reason}"
    if stop.customer_available_note:
        description += f' Customer note: "{stop.customer_available_note}"'

    ticket = ComplaintTicket.objects.create(
        customer_id=customer.unique_id,
        category_id=category.unique_id,
        subcategory_id=subcategory.unique_id if subcategory else None,
        priority_id=priority.unique_id,
        status_id=status_obj.unique_id,
        source_id=source.unique_id,
        title="Missed pickup - customer was available",
        description=description,
        wa_phone=customer.contact_no,
        profile_name=customer.customer_name,
        idempotency_key=_idempotency_key(stop),
        **{field: getattr(customer, field, None) for field in _TICKET_GEO_FIELDS},
    )
    for key, value in (
        ("incident_type", INCIDENT_TYPE),
        ("trip_reference", stop.trip_assignment_id),
    ):
        if value:
            ComplaintTicketExtraDetail.objects.create(
                ticket_id=ticket.unique_id,
                field_key=key,
                field_value=value,
                field_type="operational_context",
                is_active=True,
            )
    ComplaintStatusHistory.objects.create(
        ticket_id=ticket.unique_id,
        from_status_id=None,
        to_status_id=status_obj.unique_id,
        changed_by_system=True,
        remarks="Raised automatically: customer was available but the pickup was missed",
        visible_to_citizen=True,
    )
    apply_routing_and_sla(ticket, save=True)
    return ticket
