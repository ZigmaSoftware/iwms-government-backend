import math
from datetime import time, timedelta
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.user_creations.staffcreation import Staffcreation


class SupervisorMonthDataSeeder(BaseSeeder):
    """Seed a full month of completed trips + trip logs for `supervisor_user`.

    The supervisor home-page graph (`SupervisorWasteChart`) reads
    `daily-trip-logs`, plotting `trip_date` against `collected_weight_kg`
    (bin) and `household_collected_weight_kg` (household). To populate that
    chart we:

      1. Find the trip plan(s) owned by `supervisor_user`
         (`TripPlan.supervisor_id`). These are wired up by SupervisorUserSeeder.
      2. For each of the last ~30 days, ensure one Completed/Approved
         DailyTripAssignment exists on each supervisor plan.
      3. Create a Submitted DailyTripLog per assignment with day-varying bin +
         household weights (kept under vehicle capacity so full_clean passes).

    We deliberately DON'T create BinCollectionEvent / WasteCollection rows, so
    the weights we set on the log are preserved (the log's post-save sync only
    overrides when those source rows exist).

    Must run AFTER SupervisorUserSeeder (needs supervisor_user + its plans).
    """

    name = "supervisor_month_data"

    DAYS = 30
    DEFAULT_CAPACITY = Decimal("1000")

    def _weights_for(self, capacity, day_index, trip_date):
        """Deterministic, natural-looking bin + household weights for a day."""
        # Weekly rhythm (sin) + mild upward trend across the month.
        seasonal = 0.5 + 0.5 * math.sin(day_index / 4.5)          # 0..1
        trend = day_index / (self.DAYS * 3.0)                     # 0..~0.33
        factor = 0.45 + 0.30 * seasonal + trend                  # ~0.45..1.08
        # Lighter loads on weekends for shape.
        if trip_date.weekday() >= 5:
            factor *= 0.6
        factor = min(factor, 0.9)                                # stay well under capacity

        bin_weight = (capacity * Decimal(str(round(factor, 4)))).quantize(Decimal("0.01"))
        # Never exceed capacity - 1 (full_clean guards collected_weight vs capacity).
        bin_weight = min(bin_weight, capacity - Decimal("1"))

        household = Decimal(str(round(70 + 180 * seasonal, 2)))
        if trip_date.weekday() >= 5:
            household = (household * Decimal("0.7")).quantize(Decimal("0.01"))
        return bin_weight, household

    def run(self):
        supervisor = Staffcreation.objects.filter(
            username="supervisor_user", is_deleted=False
        ).first()
        if not supervisor:
            self.log("supervisor_user not found — run SupervisorUserSeeder first. Skipping.")
            return

        plans = list(
            TripPlan.objects.filter(
                supervisor_id=supervisor, is_deleted=False
            ).select_related("vehicle_id", "staff_template_id")
        )
        if not plans:
            self.log(
                "supervisor_user owns no trip plans — run SupervisorUserSeeder first. Skipping."
            )
            return

        today = timezone.localdate()
        created_assignments = 0
        created_logs = 0
        skipped_logs = 0
        skipped_plans = 0

        for plan in plans:
            template = plan.staff_template_id
            if not template or not template.driver_id_id or not template.operator_id_id:
                # DailyTripLog requires non-null driver + operator (autofilled
                # from the template) — skip plans that can't satisfy that.
                self.log(
                    f"Plan {plan.unique_id} has no driver/operator template — skipping."
                )
                skipped_plans += 1
                continue

            vehicle = plan.vehicle_id
            capacity = (
                (vehicle.capacity if vehicle and vehicle.capacity else None)
                or (Decimal(str(plan.max_vehicle_capacity_kg)) if plan.max_vehicle_capacity_kg else None)
                or self.DEFAULT_CAPACITY
            )
            scheduled_time = plan.scheduled_time or time(7, 0)

            # Seed HISTORY only (yesterday back ~30 days). Today is deliberately
            # skipped: today's assignment is the driver's live demo trip, and
            # attaching a Submitted log here would mark it Completed and clobber
            # the fresh Scheduled trip the DriverUserSeeder sets up.
            for offset in range(1, self.DAYS + 1):
                trip_date = today - timedelta(days=offset)

                assignment, was_created = DailyTripAssignment.objects.get_or_create(
                    trip_plan_id=plan,
                    trip_date=trip_date,
                    scheduled_time=scheduled_time,
                    is_deleted=False,
                    defaults={
                        # Required FKs must be set explicitly — the model's save()
                        # reads them (raising on unset non-null FKs) to autofill.
                        "staff_template_id": template,
                        "vehicle_id": plan.vehicle_id,
                        "state": plan.state,
                        "district": plan.district,
                        "area_type": plan.area_type,
                        "corporation": plan.corporation,
                        "municipality": plan.municipality,
                        "town_panchayat": plan.town_panchayat,
                        "panchayat_union": plan.panchayat_union,
                        "panchayat": plan.panchayat,
                        "status": DailyTripAssignment.STATUS_COMPLETED,
                        "approval_status": DailyTripAssignment.APPROVAL_APPROVED,
                    },
                )
                if was_created:
                    created_assignments += 1
                elif assignment.status == DailyTripAssignment.STATUS_CANCELLED:
                    # Can't log a cancelled trip.
                    skipped_logs += 1
                    continue

                if DailyTripLog.objects.filter(
                    trip_assignment_id=assignment, is_deleted=False
                ).exists():
                    skipped_logs += 1
                    continue

                bin_weight, household = self._weights_for(capacity, offset, trip_date)

                DailyTripLog.objects.create(
                    trip_assignment_id=assignment,
                    collected_weight_kg=bin_weight,
                    household_collected_weight_kg=household,
                    log_status=DailyTripLog.LOG_STATUS_SUBMITTED,
                    remarks=f"Supervisor demo trip log for {trip_date.isoformat()}",
                )
                created_logs += 1

        self.log(
            "---Supervisor month data seeded | "
            f"Plans: {len(plans) - skipped_plans} | "
            f"Assignments created: {created_assignments} | "
            f"Logs created: {created_logs} | Skipped logs: {skipped_logs}---"
        )
