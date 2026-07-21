from datetime import time, timedelta
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.base_models import Account


class DailyTripLogSeeder(BaseSeeder):
    name = "daily_trip_log"

    def run(self):
        assignments = (
            DailyTripAssignment.objects.select_related(
                "trip_plan_id",
                "trip_plan_id__vehicle_id",
                "staff_template_id",
                "staff_template_id__driver_id",
                "staff_template_id__operator_id",
                "alt_staff_template_id",
                "alt_staff_template_id__driver_id",
                "alt_staff_template_id__operator_id",
                "district",
            )
            .prefetch_related("waste_types")
            .filter(is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .order_by("-trip_date", "-scheduled_time")[:6]
        )

        if not assignments:
            self.log("DailyTripLogSeeder skipped (no daily trip assignments).")
            return

        statuses = [
            DailyTripLog.LOG_STATUS_DRAFT,
            DailyTripLog.LOG_STATUS_SUBMITTED,
            DailyTripLog.LOG_STATUS_VERIFIED,
        ]
        verifier = Account.objects.first()
        created = 0
        skipped = 0

        for idx, assignment in enumerate(assignments):
            if not assignment.district_id:
                skipped += 1
                continue
            if DailyTripLog.objects.filter(trip_assignment_id=assignment, is_deleted=False).exists():
                skipped += 1
                continue

            trip_plan = assignment.trip_plan_id
            vehicle = assignment.vehicle_id or getattr(trip_plan, "vehicle_id", None)
            staff_template = assignment.alt_staff_template_id or assignment.staff_template_id
            if not vehicle or not staff_template:
                skipped += 1
                continue

            capacity = vehicle.capacity or trip_plan.max_vehicle_capacity_kg or 1000
            capacity_decimal = Decimal(str(capacity))
            factor = Decimal("0.55") + (Decimal(idx) * Decimal("0.05"))
            collected_weight = min(
                capacity_decimal * factor,
                capacity_decimal - Decimal("1"),
            ).quantize(Decimal("0.01"))
            log_status = statuses[idx % len(statuses)]
            start_time = assignment.actual_start_time or time(7 + (idx % 3), 30)
            end_time = assignment.actual_end_time or time(10 + (idx % 4), 15)

            log = DailyTripLog.objects.create(
                trip_assignment_id=assignment,
                actual_start_time=start_time,
                actual_end_time=end_time,
                collected_weight_kg=collected_weight,
                remarks=f"Seeder demo {log_status.lower()} trip log for {assignment.unique_id}",
                log_status=log_status,
                verified_by=verifier if log_status == DailyTripLog.LOG_STATUS_VERIFIED else None,
                verified_at=(
                    timezone.now() - timedelta(hours=idx)
                    if log_status == DailyTripLog.LOG_STATUS_VERIFIED
                    else None
                ),
            )

            bin_qs = Bins.objects.filter(is_deleted=False).order_by("bin_name")[:3]
            if bin_qs:
                log.bin_ids.set(bin_qs)

            extra_ids = (
                getattr(staff_template, "extra_operator_id", None)
                or getattr(staff_template, "extra_operator_ids", None)
                or []
            )
            extra_staff = Staffcreation.objects.filter(staff_unique_id__in=extra_ids)
            if extra_staff:
                log.extra_operator_ids.set(extra_staff)

            created += 1

        self.log(f"---Daily trip logs seeded | Created: {created} | Skipped: {skipped}---")
