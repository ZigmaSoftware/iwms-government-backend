from app.management.commands.seeders.base import BaseSeeder
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_household_collection import DailyTripHouseholdCollection
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.signals.trip_plan_signals import _create_daily_household_collections


class DailyTripHouseholdCollectionSeeder(BaseSeeder):
    name = "daily_trip_household_collection"

    def run(self):
        created_count = 0
        assignments = (
            DailyTripAssignment.objects.filter(is_deleted=False)
            .select_related("trip_plan_id")
            .order_by("-trip_date", "unique_id")
        )

        for assignment in assignments:
            if not assignment.trip_plan_id_id:
                continue
            stops = TripPlanCollectionPoint.objects.filter(
                trip_plan_id=assignment.trip_plan_id,
                collection_type__in=[
                    TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
                    TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
                ],
                is_active=True,
                is_deleted=False,
            ).order_by("sequence")
            for stop in stops:
                created_count += _create_daily_household_collections(assignment, stop)

        examples = list(
            DailyTripHouseholdCollection.objects.filter(is_deleted=False)
            .order_by("-created_at")[:6]
        )
        status_cycle = [
            (DailyTripHouseholdCollection.STATUS_NOT_COLLECTED, "I do not collect today: customer unavailable."),
            (DailyTripHouseholdCollection.STATUS_COLLECT_LATER, "I will collect today after pending route work."),
        ]
        updated_count = 0
        for index, record in enumerate(examples):
            status, reason = status_cycle[index % len(status_cycle)]
            record.status = status
            record.status_reason = reason
            record.is_collected = False
            record.collected_at = None
            record.collected_weight_kg = None
            record.save(update_fields=[
                "status",
                "status_reason",
                "is_collected",
                "collected_at",
                "collected_weight_kg",
                "updated_at",
            ])
            updated_count += 1

        self.log(f"---DailyTripHouseholdCollection seeded | created={created_count} examples_updated={updated_count}---")
