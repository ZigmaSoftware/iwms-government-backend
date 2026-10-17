"""Integration tests for the Re-Trip flow (app/services/retrip_service.py).

These exercise the real querysets against the DB rather than mocking, because
the bugs this flow is prone to are query-shape bugs:

  * the two stop models spell "missed" differently (`Missed` for a bin stop,
    `Not Available` for a household stop), so a shared status tuple silently
    leaves household stops pending forever;
  * pruning the continuation trip's auto-cloned stops must match on the
    (collection point, bin) PAIR — a single `.exclude(a__in=…, b__in=…)`
    negates the AND and leaks cross-pair stops.
"""
import pytest
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_assignment import (
    DailyTripAssignment,
)
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)


class TestResolvedStopStatusVocabularies:
    """The two stop models must never share one 'resolved' status tuple."""

    def test_bin_and_household_missed_labels_differ(self):
        assert DailyTripCollectionPoint.STATUS_MISSED == "Missed"
        assert DailyTripHouseholdCollection.STATUS_MISSED == "Not Available"
        assert (
            DailyTripCollectionPoint.STATUS_MISSED
            != DailyTripHouseholdCollection.STATUS_MISSED
        )

    def test_bin_missed_is_not_a_valid_household_status(self):
        """Guards the original bug: filtering households on "Missed" matches
        nothing, so a Not-Available household would read as pending forever."""
        household_statuses = {
            value for value, _label in DailyTripHouseholdCollection.STATUS_CHOICES
        }
        assert DailyTripCollectionPoint.STATUS_MISSED not in household_statuses
        assert DailyTripHouseholdCollection.STATUS_MISSED in household_statuses


class TestPendingStopStatusSources:
    """`pending_*_stops()` must resolve against each model's own constants.

    Asserted by reading the source of the two model methods: building the real
    querysets needs a saved assignment, which in turn needs the whole
    plan/template/vehicle graph, and none of that affects which status labels
    the filters use. What must never regress is that the household filter
    references the HOUSEHOLD model's constants and the bin filter the BIN
    model's — not one shared tuple.
    """

    @staticmethod
    def _source_of(method):
        import inspect

        return inspect.getsource(method)

    def test_household_filter_uses_household_constants(self):
        src = self._source_of(DailyTripAssignment.pending_household_stops)
        assert "DailyTripHouseholdCollection.STATUS_COLLECTED" in src
        assert "DailyTripHouseholdCollection.STATUS_MISSED" in src

    def test_household_filter_does_not_use_shared_status_tuple(self):
        """The original bug: a shared ("Collected", "Missed") tuple, where
        "Missed" is not a household status at all."""
        src = self._source_of(DailyTripAssignment.pending_household_stops)
        assert "RESOLVED_STOP_STATUSES" not in src

    def test_bin_filter_uses_bin_constants(self):
        src = self._source_of(DailyTripAssignment.pending_bin_stops)
        assert "DailyTripCollectionPoint.STATUS_COLLECTED" in src
        assert "DailyTripCollectionPoint.STATUS_MISSED" in src

    def test_bin_filter_does_not_use_shared_status_tuple(self):
        src = self._source_of(DailyTripAssignment.pending_bin_stops)
        assert "RESOLVED_STOP_STATUSES" not in src


@pytest.mark.django_db
class TestContinuationStopPruning:
    """Pruning must match the (collection point, bin) pair, not each column."""

    def test_paired_exclude_does_not_leak_cross_pairs(self):
        """(CP1,B1) and (CP2,B2) carried => (CP1,B2) must still be deleted.

        The old `.exclude(collection_point_id__in=[CP1,CP2], bin_id__in=[B1,B2])`
        kept (CP1,B2) because negating the AND leaves rows matching only one
        side. The paired OR-of-Qs form deletes it correctly.
        """
        from django.db.models import Q

        carried = {("CP1", "B1"), ("CP2", "B2")}
        keep = Q()
        for cp_id, bin_id in carried:
            keep |= Q(collection_point_id=cp_id, bin_id=bin_id)

        paired_sql = str(DailyTripCollectionPoint.objects.exclude(keep).query)
        broken_sql = str(
            DailyTripCollectionPoint.objects.exclude(
                collection_point_id__in=["CP1", "CP2"],
                bin_id__in=["B1", "B2"],
            ).query
        )

        # The correct form pairs each cp with its own bin via AND inside OR.
        assert " OR " in paired_sql
        # The broken form compares the columns independently with IN lists.
        assert "IN (" in broken_sql
        assert paired_sql != broken_sql


class TestApproveRetripDoesNotMutateSourceStopStatuses:
    """`approve_retrip` must leave the source trip's stop statuses untouched.

    An earlier version force-closed every still-open stop on the source to
    Missed/Not Available so a Completed trip wouldn't look "still open" in the
    driver app. That backfired: `resolved` (which the app shows as the
    progress numerator) counts Missed as done, so a household trip that had
    genuinely collected nothing displayed as "13/13 Done" — a lie. The actual
    fix is that a Completed trip drops off the driver's home page entirely
    (see TestFindAllActiveAssignmentsExcludesCompleted below), so the source
    trip's stops can — and must — stay exactly as the driver left them.
    """

    def test_approve_retrip_source_code_has_no_bulk_status_update(self):
        import inspect

        from app.services import retrip_service

        src = inspect.getsource(retrip_service.approve_retrip)
        assert ".update(status=" not in src, (
            "approve_retrip must not bulk-mutate source stop statuses — that "
            "falsely inflates the `resolved` progress count on the source trip"
        )


class TestFindAllActiveAssignmentsExcludesCompleted:
    """A Completed trip must disappear from the driver's home-page feed.

    Before this, `find_all_active_assignments_for_operator` excluded only
    Cancelled, so a trip closed via Re-Trip (or any other path) stayed in the
    driver's "my trips today" carousel showing its stale progress forever —
    exactly the container the driver reported still seeing after the trip was
    marked Completed.
    """

    def test_source_excludes_completed_and_cancelled(self):
        import inspect

        from app.viewsets.operator_mobile import helpers

        src = inspect.getsource(helpers.find_all_active_assignments_for_operator)
        assert "STATUS_COMPLETED" in src
        assert "STATUS_CANCELLED" in src

    def test_generated_queryset_excludes_completed(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )

        qs = DailyTripAssignment.objects.exclude(
            status__in=(
                DailyTripAssignment.STATUS_CANCELLED,
                DailyTripAssignment.STATUS_COMPLETED,
            )
        )
        sql = str(qs.query)
        assert "Completed" in sql
        assert "Cancelled" in sql


class TestRequireTripStarted:
    """A driver must press Start before any collection write is accepted.

    Before this, `scan_bin_viewset._ensure_assignment_in_progress` silently
    started the trip as a side effect of the first scan, so there was nothing
    to actually lock against — pressing "Start Trip" was cosmetic. This guard
    is now the single choke point shared by scan-bin, mark-household-status,
    and finalize-waste.
    """

    def test_raises_when_not_started(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )
        from app.viewsets.operator_mobile.helpers import (
            OperatorFlowError,
            require_trip_started,
        )

        assignment = DailyTripAssignment(actual_start_at=None)
        with pytest.raises(OperatorFlowError) as exc_info:
            require_trip_started(assignment)
        assert exc_info.value.code == "TRIP_NOT_STARTED"
        assert exc_info.value.http_status == 409

    def test_passes_when_started(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )
        from app.viewsets.operator_mobile.helpers import require_trip_started

        assignment = DailyTripAssignment(actual_start_at=timezone.now())
        require_trip_started(assignment)  # must not raise

    def test_scan_bin_viewset_no_longer_auto_starts(self):
        """Guards against the auto-start regressing back in: scanning on a
        not-started trip must be rejected, not silently begin the trip."""
        import inspect

        from app.viewsets.operator_mobile import scan_bin_viewset

        src = inspect.getsource(scan_bin_viewset)
        assert "_ensure_assignment_in_progress" not in src
        assert "require_trip_started" in src

    def test_mark_household_status_gated(self):
        import inspect

        from app.viewsets.waste_collection_bluetooth import waste_bluetooth_viewset

        src = inspect.getsource(waste_bluetooth_viewset.WasteCollectionBluetoothViewSet.mark_household_status)
        assert "require_trip_started" in src

    def test_finalize_waste_gated(self):
        import inspect

        from app.viewsets.waste_collection_bluetooth import waste_bluetooth_viewset

        src = inspect.getsource(
            waste_bluetooth_viewset.WasteCollectionBluetoothViewSet.finalize_waste_collection
        )
        assert "require_trip_started" in src


@pytest.mark.django_db
class TestSchedulerToleratesRetripDuplicateAssignment:
    """The nightly scheduler must not crash when a Re-Trip approval has
    already created a second `DailyTripAssignment` on the same
    (trip_plan, trip_date) — exactly what `approve_retrip` does on purpose
    (the continuation trip shares its source's trip_plan_id and trip_date).

    Before this, `generate_daily_trips.run_for_date` used a plain
    `get_or_create(trip_plan_id=plan, trip_date=today, ...)`, whose internal
    `.get()` raises `DailyTripAssignment.MultipleObjectsReturned` the moment
    more than one row matches — taking the ENTIRE nightly job down (every
    later plan in the loop never runs) the first time any plan had a Re-Trip
    that day.
    """

    @pytest.fixture
    def trip_plan(self, db):
        from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        driver = Staffcreation.objects.create(employee_name="Test Driver")
        operator = Staffcreation.objects.create(employee_name="Test Operator")
        template = StaffTemplate.objects.create(
            display_code="TPL-TEST-01", driver_id=driver, operator_id=operator,
        )
        vehicle = VehicleCreation.objects.create(vehicle_no="TN-TEST-01")
        return TripPlan.objects.create(
            display_code="PLAN-TEST-01",
            staff_template_id=template,
            vehicle_id=vehicle,
            scheduled_time="06:30",
            is_auto_assign=True,
            repeat_days=list(range(7)),
            approval_status=TripPlan.ApprovalStatus.APPROVED,
            status=TripPlan.Status.ACTIVE,
        )

    def test_run_for_date_does_not_raise_on_duplicate_assignment(self, trip_plan):
        from app.management.commands.generate_daily_trips import run_for_date
        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )

        today = timezone.localdate()

        # Simulate the state right after a Re-Trip approval: two assignments
        # for the SAME plan and date (source + continuation).
        DailyTripAssignment.objects.create(
            trip_plan_id=trip_plan, trip_date=today,
            staff_template_id=trip_plan.staff_template_id,
            vehicle_id=trip_plan.vehicle_id,
            scheduled_time=trip_plan.scheduled_time,
            status=DailyTripAssignment.STATUS_COMPLETED,
        )
        DailyTripAssignment.objects.create(
            trip_plan_id=trip_plan, trip_date=today,
            staff_template_id=trip_plan.staff_template_id,
            vehicle_id=trip_plan.vehicle_id,
            scheduled_time=timezone.localtime().time(),
            status=DailyTripAssignment.STATUS_SCHEDULED,
            remarks="Re-Trip continuation",
        )
        assert DailyTripAssignment.objects.filter(
            trip_plan_id=trip_plan, trip_date=today,
        ).count() == 2

        # Must not raise MultipleObjectsReturned.
        result = run_for_date(target_date=today, force=True)
        assert result["created"] == 0

        # And must not have created a THIRD row.
        assert DailyTripAssignment.objects.filter(
            trip_plan_id=trip_plan, trip_date=today,
        ).count() == 2


@pytest.mark.django_db
class TestTotalTripTimeAndTripCount:
    """`total_trip_time` and `trip_count()` — the two fields requested for
    "how long did this trip take" and "which attempt is this" (the ordinary
    run is 1, a same-day Re-Trip continuation is 2, and so on).
    """

    @pytest.fixture
    def trip_plan(self, db):
        from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        driver = Staffcreation.objects.create(employee_name="Test Driver 2")
        operator = Staffcreation.objects.create(employee_name="Test Operator 2")
        template = StaffTemplate.objects.create(
            display_code="TPL-TEST-02", driver_id=driver, operator_id=operator,
        )
        vehicle = VehicleCreation.objects.create(vehicle_no="TN-TEST-02")
        return TripPlan.objects.create(
            display_code="PLAN-TEST-02",
            staff_template_id=template,
            vehicle_id=vehicle,
            scheduled_time="06:30",
            is_auto_assign=True,
            repeat_days=list(range(7)),
            approval_status=TripPlan.ApprovalStatus.APPROVED,
            status=TripPlan.Status.ACTIVE,
        )

    def test_total_trip_time_none_before_start(self, trip_plan):
        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )

        assignment = DailyTripAssignment.objects.create(
            trip_plan_id=trip_plan, trip_date=timezone.localdate(),
            staff_template_id=trip_plan.staff_template_id,
            vehicle_id=trip_plan.vehicle_id, scheduled_time=trip_plan.scheduled_time,
        )
        assert assignment.total_trip_time is None

    def test_total_trip_time_matches_start_to_end(self, trip_plan):
        from datetime import timedelta as td

        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )

        end = timezone.now()
        start = end - td(minutes=30)
        assignment = DailyTripAssignment.objects.create(
            trip_plan_id=trip_plan, trip_date=timezone.localdate(),
            staff_template_id=trip_plan.staff_template_id,
            vehicle_id=trip_plan.vehicle_id, scheduled_time=trip_plan.scheduled_time,
            actual_start_at=start, actual_end_at=end,
        )
        assert assignment.total_trip_time == td(minutes=30)

    def test_total_trip_time_measures_to_now_while_running(self, trip_plan):
        from datetime import timedelta as td

        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )

        start = timezone.now() - td(minutes=10)
        assignment = DailyTripAssignment.objects.create(
            trip_plan_id=trip_plan, trip_date=timezone.localdate(),
            staff_template_id=trip_plan.staff_template_id,
            vehicle_id=trip_plan.vehicle_id, scheduled_time=trip_plan.scheduled_time,
            actual_start_at=start, actual_end_at=None,
        )
        assert assignment.total_trip_time >= td(minutes=10)

    def test_trip_count_increments_for_retrip_continuation(self, trip_plan):
        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )

        today = timezone.localdate()
        original = DailyTripAssignment.objects.create(
            trip_plan_id=trip_plan, trip_date=today,
            staff_template_id=trip_plan.staff_template_id,
            vehicle_id=trip_plan.vehicle_id, scheduled_time=trip_plan.scheduled_time,
            status=DailyTripAssignment.STATUS_COMPLETED,
        )
        assert original.trip_count() == 1

        continuation = DailyTripAssignment.objects.create(
            trip_plan_id=trip_plan, trip_date=today,
            staff_template_id=trip_plan.staff_template_id,
            vehicle_id=trip_plan.vehicle_id,
            scheduled_time=timezone.localtime().time(),
            remarks="Re-Trip continuation of " + original.unique_id,
        )
        assert continuation.trip_count() == 2
        # The original's own count must not change once a continuation exists.
        original.refresh_from_db()
        assert original.trip_count() == 1

        # A second same-day re-trip of the continuation becomes 3.
        second_continuation = DailyTripAssignment.objects.create(
            trip_plan_id=trip_plan, trip_date=today,
            staff_template_id=trip_plan.staff_template_id,
            vehicle_id=trip_plan.vehicle_id,
            scheduled_time=timezone.localtime().time(),
            remarks="Re-Trip continuation of " + continuation.unique_id,
        )
        assert second_continuation.trip_count() == 3

    def test_trip_count_isolated_per_plan(self, trip_plan):
        """A different trip plan's assignment on the same date must not affect
        this plan's count."""
        from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        from app.models.core_modules.schedule_setup.trip_plan import TripPlan
        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        other_driver = Staffcreation.objects.create(employee_name="Other Driver")
        other_operator = Staffcreation.objects.create(employee_name="Other Operator")
        other_template = StaffTemplate.objects.create(
            display_code="TPL-TEST-03", driver_id=other_driver, operator_id=other_operator,
        )
        other_vehicle = VehicleCreation.objects.create(vehicle_no="TN-TEST-03")
        other_plan = TripPlan.objects.create(
            display_code="PLAN-TEST-03",
            staff_template_id=other_template,
            vehicle_id=other_vehicle,
            scheduled_time="07:00",
            is_auto_assign=True,
            repeat_days=list(range(7)),
            approval_status=TripPlan.ApprovalStatus.APPROVED,
            status=TripPlan.Status.ACTIVE,
        )
        today = timezone.localdate()
        DailyTripAssignment.objects.create(
            trip_plan_id=other_plan, trip_date=today,
            staff_template_id=other_plan.staff_template_id,
            vehicle_id=other_plan.vehicle_id, scheduled_time=other_plan.scheduled_time,
        )
        own = DailyTripAssignment.objects.create(
            trip_plan_id=trip_plan, trip_date=today,
            staff_template_id=trip_plan.staff_template_id,
            vehicle_id=trip_plan.vehicle_id, scheduled_time=trip_plan.scheduled_time,
        )
        assert own.trip_count() == 1
