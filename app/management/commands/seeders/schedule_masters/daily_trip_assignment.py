from datetime import timedelta

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.trip_plan import TripPlan

TARGET = 15


class DailyTripAssignmentSeeder(BaseSeeder):
    name = "daily_trip_assignment"

    def run(self):
        today = timezone.localdate()

        # Only use active, approved plans so the XOR constraint is satisfied via
        # the plan's own panchayat_id / ward_id (model.save() auto-fills these).
        plans = list(
            TripPlan.objects.filter(
                is_deleted=False,
                status=TripPlan.Status.ACTIVE,
                approval_status=TripPlan.ApprovalStatus.APPROVED,
            ).select_related(
                "staff_template_id",
                "waste_type_id",
                "vehicle_id",
                "panchayat_id",
                "ward_id",
            )
        )

        if not plans:
            self.log("No active approved TripPlan found — aborting.")
            return

        created_count = 0
        # Walk backwards one day at a time; for each day try every plan.
        # Stop once TARGET records are created.
        day_offset = 0
        while created_count < TARGET:
            trip_date = today - timedelta(days=day_offset)
            for plan in plans:
                if created_count >= TARGET:
                    break

                # Honour the XOR constraint: plan must supply exactly one of
                # panchayat_id or ward_id so model.save() can inherit it.
                if not plan.panchayat_id and not plan.ward_id:
                    continue

                already_exists = DailyTripAssignment.objects.filter(
                    trip_plan_id=plan,
                    trip_date=trip_date,
                    scheduled_time=plan.scheduled_time,
                    is_deleted=False,
                ).exists()

                if already_exists:
                    continue

                DailyTripAssignment.objects.create(
                    trip_plan_id=plan,
                    staff_template_id=plan.staff_template_id,
                    panchayat_id=plan.panchayat_id,   # one of these will be None;
                    ward_id=plan.ward_id,              # model.save() inherits from plan
                    waste_type_id=plan.waste_type_id,
                    vehicle_id=plan.vehicle_id,
                    trip_date=trip_date,
                    scheduled_time=plan.scheduled_time,
                    status=DailyTripAssignment.STATUS_SCHEDULED,
                    approval_status=DailyTripAssignment.APPROVAL_APPROVED,
                )
                created_count += 1

            day_offset += 1
            # Safety valve: stop after 60-day lookback to prevent infinite loop
            # if there simply aren't enough valid plans.
            if day_offset > 60:
                break

        self.log(
            f"---DailyTripAssignment seeded | target={TARGET} | created={created_count}---"
        )
