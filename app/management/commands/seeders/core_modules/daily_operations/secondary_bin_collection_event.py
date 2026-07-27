import math
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.core_modules.schedule_setup.trip_plan import TripPlan


def _day_factor(day_offset, trip_date):
    """Deterministic weekday/weekend trend (same shape used elsewhere in the
    codebase for demo history): a mild sine-wave plus a weekend dip, always
    in [0.35, 0.95] so weight stays comfortably under bin/vehicle capacity."""
    base = 0.65 + 0.25 * math.sin(day_offset / 4.5)
    if trip_date.weekday() >= 5:  # Saturday/Sunday
        base *= 0.7
    return max(0.35, min(0.95, base))


def _deterministic_outcome(sequence, day_offset):
    """~85% Collected, rest split Not Collected / Collect Later — purely a
    function of (sequence, day_offset), so re-seeding is idempotent."""
    key = (sequence + day_offset) % 10
    if key == 0:
        return BinCollectionEvent.STATUS_NOT_COLLECTED
    if key == 5:
        return BinCollectionEvent.STATUS_COLLECT_LATER
    return BinCollectionEvent.STATUS_COLLECTED


class BinCollectionEventSeeder(BaseSeeder):
    """For every bin_collection DailyTripAssignment created by
    DailyTripAssignmentSeeder (7 days x 3 districts), mark each of its
    auto-created (via signal) DailyTripCollectionPoint stops
    Collected/Missed/Skipped — mirroring the real ScanBinViewSet flow, which
    always calls mark_collected()/mark_status() BEFORE writing the
    BinCollectionEvent ledger row — then writes that ledger row. This is
    what makes DailyTripLog rows appear automatically via
    app.signals.trip_plan_signals; there is no direct DailyTripLog seeder.

    Bug fixes vs. the old seeder: it hardcoded Erode coordinates for every
    event regardless of the trip's real district, and never called
    mark_collected()/mark_status() at all — so DailyTripCollectionPoint rows
    stayed Pending forever and the log auto-submit condition (every stop
    Collected/Missed) was never satisfied."""

    name = "BinCollectionEventSeeder"

    def run(self):
        assignments = list(
            DailyTripAssignment.objects.filter(
                is_deleted=False,
                trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_BIN,
            )
            # Today is reserved for the live driver_user/scheduler-demo trip,
            # which resets its own assignment's stops/events on every seed
            # run — touching it here would fight that reset and re-create
            # events every single run instead of converging.
            .exclude(trip_date=timezone.localdate())
            .select_related("trip_plan_id", "staff_template_id", "vehicle_id")
            .order_by("trip_date")
        )
        if not assignments:
            self.log("No bin-collection DailyTripAssignments found — run DailyTripAssignmentSeeder first.")
            return

        created = 0
        for assignment in assignments:
            day_offset = _day_offset(assignment)
            operator = assignment.staff_template_id.operator_id if assignment.staff_template_id_id else None

            trip_cps = list(
                DailyTripCollectionPoint.objects.filter(
                    trip_assignment_id=assignment, is_deleted=False
                ).select_related("collection_point_id", "bin_id", "bin_id__wastetype_id").order_by("sequence")
            )
            for tcp in trip_cps:
                if not tcp.bin_id_id or not tcp.collection_point_id_id:
                    continue

                already = BinCollectionEvent.objects.filter(
                    trip_assignment_id=assignment,
                    trip_collection_point_id=tcp,
                    bin_id=tcp.bin_id,
                    collection_date=assignment.trip_date,
                ).exists()
                if already:
                    continue

                outcome = _deterministic_outcome(tcp.sequence, day_offset)
                cp = tcp.collection_point_id
                weight = None

                if outcome == BinCollectionEvent.STATUS_COLLECTED:
                    factor = Decimal(str(_day_factor(day_offset, assignment.trip_date)))
                    # Cap the per-scan fill so a multi-bin corporation trip's
                    # daily aggregate stays comfortably under any seeded
                    # vehicle's capacity (bin_capacity is a volume figure,
                    # not a literal kg ceiling).
                    fill_basis = Decimal(min(tcp.bin_id.bin_capacity, 200))
                    weight = (fill_basis * factor).quantize(Decimal("0.01"))
                    reason = ""
                    if operator:
                        tcp.mark_collected(weight_kg=weight, collected_by=operator)
                else:
                    if outcome == BinCollectionEvent.STATUS_COLLECT_LATER:
                        cp_status = DailyTripCollectionPoint.STATUS_SKIPPED
                        reason = "I will collect today after route clearance."
                    else:
                        cp_status = DailyTripCollectionPoint.STATUS_MISSED
                        reason = "I do not collect today: bin was inaccessible."
                    tcp.mark_status(status=cp_status, reason=reason, latitude=cp.latitude, longitude=cp.longitude)

                BinCollectionEvent.objects.create(
                    trip_assignment_id=assignment,
                    trip_collection_point_id=tcp,
                    collection_point_id=cp,
                    bin_id=tcp.bin_id,
                    ward=cp.wards.first(),
                    waste_type_id=tcp.bin_id.wastetype_id,
                    vehicle_id=assignment.vehicle_id,
                    collected_weight_kg=weight,
                    status=outcome,
                    status_reason=reason,
                    collection_date=assignment.trip_date,
                    driver_latitude=cp.latitude,
                    driver_longitude=cp.longitude,
                    notes=f"Seeded bin scan for {assignment.trip_date.isoformat()}.",
                    is_active=True,
                    is_deleted=False,
                )
                created += 1

        self.log(f"---Bin collection events seeded ({created} created)---")


def _day_offset(assignment):
    return (timezone.localdate() - assignment.trip_date).days
