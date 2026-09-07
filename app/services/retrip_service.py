"""Re-Trip: close a trip that still has stops, and carry the rest to a new one.

Shared by the driver endpoint that raises the request
(`app/viewsets/operator_mobile/trip_lifecycle_viewset.py`) and the supervisor
endpoint that decides it
(`app/viewsets/core_modules/daily_operations/trip_retrip_viewset.py`), so the
snapshot format and the carry-over rules live in exactly one place.

Carry-over rules differ by collection type, per the product spec:
  * household — every remaining household moves to the continuation trip.
  * bin       — the supervisor picks which collection points move; the rest are
                dropped for the day.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.services.staff_notification_service import notify_staff


def build_pending_snapshot(assignment):
    """What is still outstanding, in a shape the supervisor screen can render."""
    bins = [
        {
            "unique_id": stop.unique_id,
            "sequence": stop.sequence,
            "status": stop.status,
            "collection_point_id": stop.collection_point_id_id,
            "name": getattr(stop.collection_point_id, "cp_name", None),
            "bin_id": stop.bin_id_id,
        }
        for stop in assignment.pending_bin_stops().select_related("collection_point_id")
    ]
    households = [
        {
            "unique_id": stop.unique_id,
            "sequence": stop.sequence,
            "status": stop.status,
            "customer_id": stop.customer_id_id,
            "name": getattr(stop.customer_id, "customer_name", None),
        }
        for stop in assignment.pending_household_stops().select_related("customer_id")
    ]
    return {"collection_points": bins, "households": households}


def _crew_of(assignment):
    """Driver + operator on the effective (possibly substituted) template."""
    template = assignment.alt_staff_template_id or assignment.staff_template_id
    if template is None:
        return []
    return [
        staff
        for staff in (
            getattr(template, "driver_id", None),
            getattr(template, "operator_id", None),
        )
        if staff is not None
    ]


def _supervisors_for(assignment):
    """Who should be asked to approve.

    `TripPlan.supervisor_id` is the same field the supervisor app filters on
    with `?mine=true` (daily_trip_assignment_viewset.py:141), so notifying it
    guarantees the request lands in the list the approver is already watching.
    """
    plan = assignment.trip_plan_id
    supervisor = getattr(plan, "supervisor_id", None) if plan else None
    return [supervisor] if supervisor is not None else []


@transaction.atomic
def request_retrip(assignment, *, requested_by, reason):
    """Driver asks to close `assignment` early. Trip stays In Progress."""
    snapshot = build_pending_snapshot(assignment)

    request = TripRetripRequest.objects.create(
        assignment=assignment,
        requested_by=requested_by,
        reason=reason,
        pending_bin_count=len(snapshot["collection_points"]),
        pending_household_count=len(snapshot["households"]),
        pending_snapshot=snapshot,
    )

    pending_total = request.pending_bin_count + request.pending_household_count
    for supervisor in _supervisors_for(assignment):
        notify_staff(
            supervisor,
            StaffNotification.TYPE_RETRIP_REQUESTED,
            "Re-Trip requested",
            f"{getattr(requested_by, 'employee_name', 'A driver')} asked to end "
            f"{assignment.unique_id} with {pending_total} stop(s) left. Reason: {reason}",
            data={
                "event": "retrip_requested",
                "retrip_request_id": request.unique_id,
                "assignment_id": assignment.unique_id,
                "pending_bin_count": request.pending_bin_count,
                "pending_household_count": request.pending_household_count,
            },
        )

    return request


def _create_continuation_assignment(
    source, *, vehicle_id=None, alt_staff_template_id=None, remarks=None
):
    """A fresh assignment on the SAME trip plan, carrying the leftover work.

    `DailyTripAssignment.save()` clones every plan stop on create (and fans a
    household plan out to every customer in the ward), so the caller prunes
    down to the carried-over set afterwards — that is far safer than
    special-casing the post_save signal.

    `vehicle_id`/`alt_staff_template_id` let a caller swap in a replacement
    vehicle/crew instead of carrying the source's own (used by a vehicle
    breakdown continuation); default to the source's when omitted (the plain
    Re-Trip case).
    """
    continuation = DailyTripAssignment(
        trip_plan_id=source.trip_plan_id,
        staff_template_id=source.staff_template_id,
        alt_staff_template_id=alt_staff_template_id or source.alt_staff_template_id,
        vehicle_id=vehicle_id or source.vehicle_id,
        trip_date=source.trip_date,
        # Continuation starts now, not at the original slot.
        scheduled_time=timezone.localtime().time(),
        status=DailyTripAssignment.STATUS_SCHEDULED,
        approval_status=DailyTripAssignment.APPROVAL_APPROVED,
        remarks=remarks or f"Re-Trip continuation of {source.unique_id}",
    )
    # Carry the SOURCE trip's waste types and wards, which may be narrower than
    # the plan's. `save()` only falls back to the plan's when these are empty,
    # so setting them first keeps the continuation scoped like its parent.
    continuation.save()
    continuation.waste_types.set(source.waste_types.all())
    continuation.wards.set(source.wards.all())
    return continuation


@transaction.atomic
def create_breakdown_continuation(
    source, *, vehicle_id, alt_staff_template_id, collection_point_ids=None
):
    """Vehicle-breakdown counterpart of `approve_retrip`: open a continuation
    crewed by the replacement vehicle/driver/operator, carrying the same-day
    leftover stops.

    Carry-over rules mirror Re-Trip: household trips always carry every
    pending stop; bin trips carry only `collection_point_ids` (required —
    the caller, e.g. the breakdown-verify screen, must let the supervisor
    pick which collection points move).
    """
    pending_bins = list(source.pending_bin_stops())
    pending_households = list(source.pending_household_stops())

    if collection_point_ids is not None:
        selected = set(collection_point_ids)
        pending_bin_ids = {stop.unique_id for stop in pending_bins}
        unknown = selected - pending_bin_ids
        if unknown:
            raise ValueError("Selected collection point is not pending on this trip.")
        pending_bins = [stop for stop in pending_bins if stop.unique_id in selected]

    if not pending_bins and not pending_households:
        raise ValueError("There are no pending stops to carry over.")

    carry_bin_keys = {
        (stop.collection_point_id_id, stop.bin_id_id) for stop in pending_bins
    }
    carry_customer_ids = {stop.customer_id_id for stop in pending_households}

    continuation = _create_continuation_assignment(
        source,
        vehicle_id=vehicle_id,
        alt_staff_template_id=alt_staff_template_id,
        remarks=f"Vehicle Breakdown continuation of {source.unique_id}",
    )

    cloned_bins = DailyTripCollectionPoint.objects.filter(trip_assignment_id=continuation)
    if carry_bin_keys:
        keep = Q()
        for cp_id, bin_id in carry_bin_keys:
            keep |= Q(collection_point_id=cp_id, bin_id=bin_id)
        cloned_bins.exclude(keep).delete()
    else:
        cloned_bins.delete()

    cloned_households = DailyTripHouseholdCollection.objects.filter(
        trip_assignment_id=continuation
    )
    if carry_customer_ids:
        cloned_households.exclude(customer_id__in=carry_customer_ids).delete()
    else:
        cloned_households.delete()

    DailyTripCollectionPoint.objects.filter(
        unique_id__in=[stop.unique_id for stop in pending_bins]
    ).update(carried_to_assignment=continuation)
    DailyTripHouseholdCollection.objects.filter(
        unique_id__in=[stop.unique_id for stop in pending_households]
    ).update(carried_to_assignment=continuation)

    for staff in _crew_of(source):
        notify_staff(
            staff,
            StaffNotification.TYPE_RETRIP_APPROVED,
            "Vehicle replaced — new trip assigned",
            f"{source.unique_id} has a vehicle breakdown replacement trip "
            f"({continuation.unique_id}) assigned.",
            data={
                "event": "breakdown_continuation",
                "assignment_id": source.unique_id,
                "new_assignment_id": continuation.unique_id,
            },
        )

    return continuation


@transaction.atomic
def approve_retrip(request, *, reviewed_by, collection_point_ids=None, remarks=None):
    """Supervisor approves: end the old trip, open a continuation trip.

    `collection_point_ids` are `DailyTripCollectionPoint.unique_id`s the
    supervisor ticked. Ignored for a household trip, where everything carries.
    Returns the new assignment.
    """
    source = request.assignment

    # Resolve what carries over from LIVE data, not the snapshot — a stop may
    # have been collected between the request and this approval.
    pending_bins = list(source.pending_bin_stops())
    pending_households = list(source.pending_household_stops())

    if collection_point_ids is not None:
        selected = set(collection_point_ids)
        pending_bins = [stop for stop in pending_bins if stop.unique_id in selected]

    # A bin stop is identified by the (collection point, bin) PAIR — one
    # collection point can hold several bins, each its own stop.
    carry_bin_keys = {
        (stop.collection_point_id_id, stop.bin_id_id) for stop in pending_bins
    }
    carry_customer_ids = {stop.customer_id_id for stop in pending_households}

    continuation = _create_continuation_assignment(source)

    # Prune the auto-cloned stops down to only what was carried over.
    #
    # Match on the pair, one Q per carried stop. A single
    # `.exclude(collection_point_id__in=…, bin_id__in=…)` would be wrong twice
    # over: exclude() negates the AND of its lookups, so a stop that shares a
    # bin with a carried stop but a different collection point would survive;
    # and `__in` never matches a NULL bin_id, so bin-less stops would leak too.
    cloned_bins = DailyTripCollectionPoint.objects.filter(trip_assignment_id=continuation)
    if carry_bin_keys:
        keep = Q()
        for cp_id, bin_id in carry_bin_keys:
            keep |= Q(collection_point_id=cp_id, bin_id=bin_id)
        cloned_bins.exclude(keep).delete()
    else:
        cloned_bins.delete()

    cloned_households = DailyTripHouseholdCollection.objects.filter(
        trip_assignment_id=continuation
    )
    if carry_customer_ids:
        cloned_households.exclude(customer_id__in=carry_customer_ids).delete()
    else:
        cloned_households.delete()

    # Point the SOURCE stops that carried over at the continuation, so the
    # Daily Trip Plan / Daily Trip Log screens can show "Assigned to Next
    # Trip" instead of a bare Pending with no explanation. Bulk `.update()` —
    # not `.save()` per instance — so it doesn't touch `status`/`updated_at`.
    DailyTripCollectionPoint.objects.filter(
        unique_id__in=[stop.unique_id for stop in pending_bins]
    ).update(carried_to_assignment=continuation)
    DailyTripHouseholdCollection.objects.filter(
        unique_id__in=[stop.unique_id for stop in pending_households]
    ).update(carried_to_assignment=continuation)

    # The original trip is done. Its stops are deliberately left exactly as
    # they are — most stay Pending, since a carried-over stop was genuinely
    # neither collected nor missed today, it moved to the continuation. Do NOT
    # force them to "Missed"/"Not Available": that status feeds the progress
    # count (`resolved` includes Missed), so bulk-closing them would falsely
    # show the source trip as "13/13 done" when nothing was actually
    # collected. The correct fix for a Completed trip is that it drops off the
    # driver's home page entirely (see
    # `find_all_active_assignments_for_operator`), not that its numbers lie.
    source.mark_ended()

    # If a DailyTripLog already exists for the source (created while the trip
    # was still open), refresh it so its own actual_start_time/actual_end_time
    # pick up what mark_ended() just stamped on the assignment.
    # autofill_from_assignment() only fills those fields when they're still
    # empty, so nothing re-saving here would leave the log's end time stuck at
    # null forever — the Trip Log report would show a Completed-looking trip
    # with a blank End Time.
    source_log = getattr(source, "daily_trip_log", None)
    if source_log is not None:
        source_log.save()

    request.mark_reviewed(
        status=TripRetripRequest.STATUS_APPROVED,
        by=reviewed_by,
        remarks=remarks,
        new_assignment=continuation,
    )

    # Count what actually landed on the continuation, not what we intended to
    # carry — the plan may no longer contain a stop the driver still had.
    carried = cloned_bins.count() + cloned_households.count()
    for staff in _crew_of(source):
        notify_staff(
            staff,
            StaffNotification.TYPE_RETRIP_APPROVED,
            "Re-Trip approved",
            f"{source.unique_id} has been closed. A new trip "
            f"({continuation.unique_id}) with {carried} stop(s) is now on your list.",
            data={
                "event": "retrip_approved",
                "retrip_request_id": request.unique_id,
                "assignment_id": source.unique_id,
                "new_assignment_id": continuation.unique_id,
            },
        )

    return continuation


@transaction.atomic
def proceed_to_next_trip(assignment, *, actor, collection_point_ids=None, remarks):
    """Web one-step version: a supervisor/admin closes `assignment` and opens
    the continuation directly, instead of a driver requesting and a
    supervisor approving separately.

    Reuses `request_retrip`/`approve_retrip` so the audit trail (a Pending
    TripRetripRequest, immediately Approved) and the carry-over rules stay in
    exactly one place. Returns (request, continuation_assignment).
    """
    if assignment.status in (
        DailyTripAssignment.STATUS_COMPLETED,
        DailyTripAssignment.STATUS_CANCELLED,
    ):
        raise ValueError("This trip is already closed.")

    request = request_retrip(assignment, requested_by=actor, reason=remarks)
    continuation = approve_retrip(
        request,
        reviewed_by=actor,
        collection_point_ids=collection_point_ids,
        remarks=remarks,
    )
    return request, continuation


@transaction.atomic
def reject_retrip(request, *, reviewed_by, remarks=None):
    """Supervisor declines: the trip stays open and the driver keeps going."""
    request.mark_reviewed(
        status=TripRetripRequest.STATUS_REJECTED,
        by=reviewed_by,
        remarks=remarks,
    )

    for staff in _crew_of(request.assignment):
        notify_staff(
            staff,
            StaffNotification.TYPE_RETRIP_REJECTED,
            "Re-Trip declined",
            f"Your request to end {request.assignment.unique_id} was declined."
            + (f" {remarks}" if remarks else " Please continue the remaining stops."),
            data={
                "event": "retrip_rejected",
                "retrip_request_id": request.unique_id,
                "assignment_id": request.assignment.unique_id,
            },
        )

    return request
