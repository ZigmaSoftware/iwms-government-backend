"""Create one plan's DailyTripAssignment (+ its stops) for a date.

Shared by the nightly/manual generator (`generate_daily_trips.run_for_date`)
and the supervisor app's "Assign trip" action
(`DailyTripAssignmentViewSet.generate_selected`), so both build a trip the
same way.
"""

from django.db import transaction

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.utils.hierarchy import FLAT_GEO_FIELDS
from app.utils.plain_ref import ref_id


def existing_assignment_for_plan(plan, target_date):
    """The oldest live assignment for (plan, date), or None.

    Not a plain get(): a Re-Trip continuation is deliberately a second
    assignment on the same (trip_plan_id, trip_date), and a deleted trip must
    not count as the day's assignment or the plan could never be assigned
    again that day.
    """
    return (
        DailyTripAssignment.objects.filter(
            trip_plan_id=ref_id(plan),
            trip_date=target_date,
            is_deleted=False,
        )
        .order_by("created_at")
        .first()
    )


def _clone_plan_stops(plan, assignment):
    """Safety net behind the post_save signal that already clones the stops;
    both paths use get_or_create, so nothing is ever duplicated."""
    from app.signals.trip_plan_signals import _create_daily_household_collections

    stops = TripPlanCollectionPoint.objects.filter(
        trip_plan_id=plan.unique_id,
        collection_type=plan.collection_type,
        is_active=True,
        is_deleted=False,
    ).order_by("sequence")
    for stop in stops:
        if stop.collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BIN:
            if not stop.collection_point_id:
                continue
            DailyTripCollectionPoint.objects.get_or_create(
                trip_assignment_id=ref_id(assignment),
                collection_point_id=ref_id(stop.collection_point),
                bin_id=ref_id(stop.bin),
                defaults={
                    "sequence": stop.sequence,
                    "status": DailyTripCollectionPoint.STATUS_PENDING,
                },
            )
        elif stop.collection_type in {
            TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
            TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
        }:
            _create_daily_household_collections(assignment, stop)


@transaction.atomic
def generate_assignment_for_plan(plan: TripPlan, target_date, created_by=None):
    """Create (or fetch) the plan's assignment for `target_date`.

    Returns (assignment, created, stop_count) where stop_count is the number
    of collection-point + household rows the assignment now has.
    """
    # Share the plan lock with declare_no_collection so generation cannot
    # race a service cancellation after checking the notice.
    from app.services.daily_service_notice import active_notice_for_plan, DailyServiceNoticeError

    plan = TripPlan.objects.select_for_update().get(unique_id=plan.unique_id)
    if active_notice_for_plan(plan.unique_id, target_date):
        raise DailyServiceNoticeError("No collection has been declared for this date.")
    assignment = existing_assignment_for_plan(plan, target_date)
    created = assignment is None
    if created:
        defaults = {
            "staff_template_id": plan.staff_template_id,
            "vehicle_id": plan.vehicle_id,
            "scheduled_time": plan.scheduled_time,
        }
        for field in FLAT_GEO_FIELDS:
            defaults[f"{field}_id"] = getattr(plan, f"{field}_id", None)
        actor = getattr(created_by, "pk", created_by)
        if actor:
            defaults["created_by"] = str(actor)
            defaults["updated_by"] = str(actor)
        assignment = DailyTripAssignment.objects.create(
            trip_plan_id=plan.unique_id,
            trip_date=target_date,
            **defaults,
        )
        if not assignment.waste_type_ids:
            assignment.waste_type_ids = list(plan.waste_type_ids or [])
            assignment.save(update_fields=["waste_type_ids"])
        _clone_plan_stops(plan, assignment)

    stop_count = (
        DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=ref_id(assignment), is_deleted=False
        ).count()
        + DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id=ref_id(assignment), is_deleted=False
        ).count()
    )
    return assignment, created, stop_count
