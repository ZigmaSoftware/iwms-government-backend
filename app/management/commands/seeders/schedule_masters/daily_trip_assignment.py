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

        # Only use active, approved plans with a location node set.
        plans = list(
            TripPlan.objects.filter(
                is_deleted=False,
                status=TripPlan.Status.ACTIVE,
                approval_status=TripPlan.ApprovalStatus.APPROVED,
            ).select_related(
                "staff_template_id",
                "waste_type_id",
                "vehicle_id",
                "location_node",
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

                if not plan.location_node_id:
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
                    location_node=plan.location_node,
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
