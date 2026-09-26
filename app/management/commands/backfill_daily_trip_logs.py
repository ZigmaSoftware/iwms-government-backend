from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.utils.plain_ref import ref_id


class Command(BaseCommand):
    help = "Create missing DailyTripLog rows for daily trip assignments that have collection points."

    @transaction.atomic
    def handle(self, *args, **options):
        assignments = DailyTripAssignment.objects.filter(
            is_deleted=False,
        ).exclude(
            status=DailyTripAssignment.STATUS_CANCELLED,
        ).exclude(
            # DailyTripLog.trip_assignment_id is a plain unique_id (no join).
            unique_id__in=DailyTripLog.objects.values("trip_assignment_id"),
        )

        created = 0
        submitted = 0
        skipped = 0
        for assignment in assignments:
            children = assignment.trip_collection_points.filter(is_deleted=False)
            if not children.exists():
                skipped += 1
                continue

            all_collected = not children.filter(is_collected=False).exists()
            if all_collected and assignment.status != DailyTripAssignment.STATUS_COMPLETED:
                assignment.mark_completed_if_all_cps_collected()

            total_weight = children.aggregate(total=Sum("collected_weight_kg"))["total"] or 0
            vehicle_capacity = getattr(getattr(assignment, "vehicle", None), "capacity", None)
            trip_capacity = getattr(getattr(assignment, "trip_plan", None), "max_vehicle_capacity_kg", None)
            capacity = vehicle_capacity or trip_capacity
            exceeds_capacity = (
                bool(capacity)
                and total_weight
                and Decimal(str(total_weight)) > Decimal(str(capacity))
            )
            stored_weight = None if exceeds_capacity else total_weight
            log_status = (
                DailyTripLog.LOG_STATUS_SUBMITTED
                if all_collected and stored_weight
                else DailyTripLog.LOG_STATUS_DRAFT
            )
            remarks = (
                "Backfilled from daily trip collection points; total weight exceeds capacity."
                if exceeds_capacity
                else "Backfilled from daily trip collection points."
            )

            DailyTripLog.objects.create(
                trip_assignment_id=ref_id(assignment),
                collected_weight_kg=stored_weight,
                log_status=log_status,
                remarks=remarks,
            )
            created += 1
            if log_status == DailyTripLog.LOG_STATUS_SUBMITTED:
                submitted += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Daily trip log backfill complete. "
                f"created={created} submitted={submitted} skipped={skipped}"
            )
        )
