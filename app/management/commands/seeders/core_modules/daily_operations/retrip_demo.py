from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.core_modules.daily_operations.daily_trip_assignment import (
    DEMO_STAFF_USERNAMES,
    FLAT_GEO_FIELDS,
)
from app.management.commands.seeders.core_modules.daily_operations.waste_collection import WASTE_PRESETS
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.waste_collection import WasteCollection
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.services import retrip_service

# "Today" is the same reservation `DriverUserSeeder`/`SchedulerDemoSeeder` use
# for their own hand-curated live state — both `BinCollectionEventSeeder` and
# `WasteCollectionSeeder` skip every assignment dated today, so building this
# demo's assignments on today's date is what keeps their fully-resolved
# (Collected/Skipped/Missed on every stop) history sweep from touching —
# and flattening — the deliberately partial state this seeder creates.
REMARKS = "Truck full — proceeding to weighment. Seeded Re-Trip demo scenario."


def _split_for_partial_completion(total):
    """How many stops to mark collected vs. leave pending. Mirrors the exact
    shape from the product ask when there's enough to split — 5 stops, 3
    collected, 2 left for the next trip. Most seeded trip plans in a smaller
    demo dataset only carry a single stop; rather than skip those entirely,
    a 1-stop trip is left fully pending, which is still a genuine (if less
    illustrative) 'one outstanding stop, carry it over' scenario."""
    if total <= 0:
        return None
    if total == 1:
        return 0, 1
    pending = min(total - 1, max(2, total // 3))
    return total - pending, pending


class RetripDemoSeeder(BaseSeeder):
    """Seeds the Re-Trip / 'Proceed with Next Trip' scenarios end-to-end —
    the web feature added alongside `carried_to_assignment` has nothing to
    show against without this, since every other seeder resolves 100% of a
    trip's stops (see BinCollectionEventSeeder/WasteCollectionSeeder) and
    nothing anywhere creates a TripRetripRequest.

    Reserves 4 distinct, already-seeded TripPlans (3 bin + 1 household,
    excluding the driver_user/operator_user demo plans) for one dedicated
    "today" assignment each, so it never collides with the generic 7-day
    history walk:

      1. Bin trip     — partial completion, `proceed_to_next_trip()` (web
                         one-step): continuation created, selected pending
                         CPs get `carried_to_assignment` set, source ends.
      2. Household trip — partial completion, `proceed_to_next_trip()` with
                         no CP selection: every remaining household
                         auto-carries (the product rule for households).
      3. Bin trip     — partial completion, `request_retrip()` only: stays
                         In Progress with a Pending TripRetripRequest — the
                         scenario both for testing the Re-Trip Requests
                         approval queue AND for manually exercising the new
                         checkbox-picker/"Proceed with Next Trip" button on
                         an untouched, still-open trip.
      4. Bin trip     — partial completion, `request_retrip()` then
                         `reject_retrip()`: stays In Progress with a
                         Rejected TripRetripRequest, for queue history/filter
                         coverage.

    Idempotent: re-running finds the same (trip_plan, today) assignments via
    get_or_create and skips any stage whose result already exists (a
    TripRetripRequest for that assignment, or a source already Completed).
    """

    name = "retrip_demo"

    # ------------------------------------------------------------------
    def run(self):
        today = timezone.localdate()

        bin_plans = self._eligible_plans(TripPlan.COLLECTION_TYPE_BIN, limit=3)
        household_plans = self._eligible_plans(TripPlan.COLLECTION_TYPE_HOUSEHOLD, limit=1)

        if len(bin_plans) < 3:
            self.log_error(
                f"Need 3 distinct bin-collection TripPlans with complete staff/vehicle, "
                f"found {len(bin_plans)} — seed schedule-setup first. Skipping bin scenarios."
            )
        if len(household_plans) < 1:
            self.log_error(
                "Need 1 household-collection TripPlan with complete staff/vehicle — "
                "seed schedule-setup and customer-masters first. Skipping household scenario."
            )

        summary = []
        if len(bin_plans) >= 1:
            summary.append(self._run_proceed_next_trip_scenario(bin_plans[0], today, is_household=False))
        if len(household_plans) >= 1:
            summary.append(self._run_proceed_next_trip_scenario(household_plans[0], today, is_household=True))
        if len(bin_plans) >= 2:
            summary.append(self._run_pending_request_scenario(bin_plans[1], today))
        if len(bin_plans) >= 3:
            summary.append(self._run_rejected_request_scenario(bin_plans[2], today))

        self.log("---Re-Trip demo scenarios seeded: " + "; ".join(s for s in summary if s) + "---")

    # ------------------------------------------------------------------
    def _eligible_plans(self, collection_type, limit):
        qs = (
            TripPlan.objects.filter(
                is_deleted=False,
                status=TripPlan.Status.ACTIVE,
                approval_status=TripPlan.ApprovalStatus.APPROVED,
                collection_type=collection_type,
            )
            .exclude(staff_template_id__driver_id__username__in=DEMO_STAFF_USERNAMES)
            .select_related(
                "staff_template_id",
                "staff_template_id__driver_id",
                "staff_template_id__operator_id",
                "vehicle_id",
                "supervisor_id",
                "district",
            )
            .prefetch_related("waste_types", "wards")
        )
        if collection_type == TripPlan.COLLECTION_TYPE_BIN:
            # Most demo datasets have plenty of 1-stop bin plans and only a
            # handful with more — prefer the richer ones first so the
            # flagship "collect some, carry the rest" scenario gets a plan
            # with more than one stop to split when one exists, instead of
            # picking whichever plan happens to sort first by unique_id.
            qs = qs.annotate(
                _stop_count=Count(
                    "plan_collection_points",
                    filter=Q(plan_collection_points__is_deleted=False),
                    distinct=True,
                )
            ).order_by("-_stop_count", "unique_id")
        else:
            qs = qs.order_by("unique_id")

        eligible = [
            plan
            for plan in qs
            if plan.district_id
            and plan.staff_template_id
            and plan.staff_template_id.driver_id_id
            and plan.staff_template_id.operator_id_id
            and plan.vehicle_id_id
        ]
        return eligible[:limit]

    # ------------------------------------------------------------------
    def _get_or_create_today_assignment(self, plan, today):
        """Not a plain get_or_create: once a scenario below has called
        proceed_to_next_trip()/approve_retrip() on this (plan, today) pair, a
        SECOND assignment — the continuation — legitimately exists for the
        same key, and get_or_create()'s implicit .get() would raise
        MultipleObjectsReturned on the next seed run. Same trap and same fix
        as generate_daily_trips.py: treat the oldest row as 'the' assignment
        for this scenario and only create when none exists yet."""
        existing = (
            DailyTripAssignment.objects.filter(trip_plan_id=plan, trip_date=today, is_deleted=False)
            .order_by("created_at")
            .first()
        )
        if existing is not None:
            return existing, False

        template = plan.staff_template_id
        assignment = DailyTripAssignment.objects.create(
            trip_plan_id=plan,
            trip_date=today,
            staff_template_id=template,
            vehicle_id=plan.vehicle_id,
            **{field: getattr(plan, field, None) for field in FLAT_GEO_FIELDS},
            scheduled_time=plan.scheduled_time,
            status=DailyTripAssignment.STATUS_SCHEDULED,
            approval_status=DailyTripAssignment.APPROVAL_APPROVED,
            remarks=REMARKS,
        )
        assignment.waste_types.set(plan.waste_types.all())
        assignment.wards.set(plan.wards.all())
        return assignment, True

    def _mark_in_progress(self, assignment, today):
        if assignment.status == DailyTripAssignment.STATUS_IN_PROGRESS:
            return
        started_at = timezone.make_aware(
            datetime.combine(today, assignment.scheduled_time)
        ) + timedelta(minutes=5)
        assignment.mark_started(at=started_at)

    # ------------------------------------------------------------------
    def _partially_collect_bin_stops(self, assignment):
        """Collect the first N stops (by sequence), leave the rest Pending.
        Returns (collected_count, pending_stop_unique_ids)."""
        operator = assignment.staff_template_id.operator_id if assignment.staff_template_id_id else None
        stops = list(
            DailyTripCollectionPoint.objects.filter(trip_assignment_id=assignment, is_deleted=False)
            .select_related("collection_point_id", "bin_id")
            .order_by("sequence")
        )
        split = _split_for_partial_completion(len(stops))
        if split is None:
            return 0, []
        collected_count, _pending_count = split

        pending_ids = []
        for index, stop in enumerate(stops):
            if index < collected_count:
                if stop.is_collected:
                    continue
                weight = stop.bin_id.bin_capacity if stop.bin_id_id else 50
                if operator:
                    stop.mark_collected(weight_kg=min(weight, 150), collected_by=operator)
            else:
                pending_ids.append(stop.unique_id)
        return collected_count, pending_ids

    def _partially_collect_household_stops(self, assignment):
        """Collect the first N household stops (by sequence, via a real
        WasteCollection row — same mechanism WasteCollectionSeeder uses),
        leave the rest Pending. Returns collected_count."""
        stops = list(
            DailyTripHouseholdCollection.objects.filter(trip_assignment_id=assignment, is_deleted=False)
            .select_related("customer_id")
            .order_by("sequence")
        )
        split = _split_for_partial_completion(len(stops))
        if split is None:
            return 0
        collected_count, _pending_count = split

        made = 0
        for index, stop in enumerate(stops[:collected_count]):
            if stop.is_collected:
                continue
            if WasteCollection.objects.filter(
                customer=stop.customer_id, trip_assignment_id=assignment
            ).exists():
                continue
            wet, dry, mixed, sanitary = WASTE_PRESETS[index % len(WASTE_PRESETS)]
            WasteCollection.objects.create(
                customer=stop.customer_id,
                trip_assignment_id=assignment,
                collection_date=assignment.trip_date,
                wet_waste=wet,
                dry_waste=dry,
                mixed_waste=mixed,
                sanitary_waste=sanitary,
                # post_save signal marks `stop` collected + syncs the log.
            )
            made += 1
        return made

    # ------------------------------------------------------------------
    def _run_proceed_next_trip_scenario(self, plan, today, *, is_household):
        assignment, _created = self._get_or_create_today_assignment(plan, today)
        if assignment.status in (DailyTripAssignment.STATUS_COMPLETED, DailyTripAssignment.STATUS_CANCELLED):
            return f"{assignment.unique_id} already proceeded"

        self._mark_in_progress(assignment, today)

        if is_household:
            collected = self._partially_collect_household_stops(assignment)
            if collected == 0 and not assignment.has_pending_stops():
                return f"{assignment.unique_id} has no household stops to demo"
            actor = plan.supervisor_id or plan.staff_template_id.operator_id
            _request, continuation = retrip_service.proceed_to_next_trip(
                assignment, actor=actor, collection_point_ids=None, remarks=REMARKS,
            )
        else:
            collected, pending_ids = self._partially_collect_bin_stops(assignment)
            if not pending_ids:
                return f"{assignment.unique_id} has no pending collection points to demo"
            actor = plan.supervisor_id or plan.staff_template_id.operator_id
            _request, continuation = retrip_service.proceed_to_next_trip(
                assignment, actor=actor, collection_point_ids=pending_ids, remarks=REMARKS,
            )

        kind = "household" if is_household else "bin"
        return f"{assignment.unique_id} ({kind}, {collected} collected) -> continuation {continuation.unique_id}"

    def _run_pending_request_scenario(self, plan, today):
        assignment, _created = self._get_or_create_today_assignment(plan, today)
        if assignment.retrip_requests.filter(status="Pending").exists():
            return f"{assignment.unique_id} already has a pending Re-Trip request"
        if assignment.status in (DailyTripAssignment.STATUS_COMPLETED, DailyTripAssignment.STATUS_CANCELLED):
            return f"{assignment.unique_id} already closed — skip pending-request demo"

        self._mark_in_progress(assignment, today)
        collected, pending_ids = self._partially_collect_bin_stops(assignment)
        if not pending_ids:
            return f"{assignment.unique_id} has no pending collection points to demo"

        driver = assignment.staff_template_id.driver_id if assignment.staff_template_id_id else None
        retrip_service.request_retrip(assignment, requested_by=driver, reason=REMARKS)
        return f"{assignment.unique_id} (bin, {collected} collected) -> Pending Re-Trip request raised"

    def _run_rejected_request_scenario(self, plan, today):
        assignment, _created = self._get_or_create_today_assignment(plan, today)
        if assignment.retrip_requests.filter(status="Rejected").exists():
            return f"{assignment.unique_id} already has a rejected Re-Trip request"
        if assignment.status in (DailyTripAssignment.STATUS_COMPLETED, DailyTripAssignment.STATUS_CANCELLED):
            return f"{assignment.unique_id} already closed — skip rejected-request demo"

        self._mark_in_progress(assignment, today)
        collected, pending_ids = self._partially_collect_bin_stops(assignment)
        if not pending_ids:
            return f"{assignment.unique_id} has no pending collection points to demo"

        driver = assignment.staff_template_id.driver_id if assignment.staff_template_id_id else None
        supervisor = plan.supervisor_id
        request = retrip_service.request_retrip(assignment, requested_by=driver, reason=REMARKS)
        retrip_service.reject_retrip(request, reviewed_by=supervisor, remarks="Please finish the remaining stops today.")
        return f"{assignment.unique_id} (bin, {collected} collected) -> Rejected Re-Trip request"
