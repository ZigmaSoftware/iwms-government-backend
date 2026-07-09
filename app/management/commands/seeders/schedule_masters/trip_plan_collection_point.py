from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.utils.hierarchy import HIERARCHY_FIELDS, selected_hierarchy_values


class TripPlanCollectionPointSeeder(BaseSeeder):
    name = "trip_plan_collection_point"

    def run(self):
        total_created = 0
        plans = TripPlan.objects.filter(is_deleted=False, status=TripPlan.Status.ACTIVE)

        for plan in plans:
            stale_stops = TripPlanCollectionPoint.objects.filter(trip_plan_id=plan).exclude(
                collection_type=plan.collection_type,
            ).order_by("sequence", "unique_id")
            for offset, stop in enumerate(stale_stops, start=1):
                stop.sequence = 9000 + offset
                stop.is_active = False
                stop.is_deleted = True
                stop.save(update_fields=["sequence", "is_active", "is_deleted", "updated_at"])
            sequence = 0
            hierarchy = selected_hierarchy_values(plan)

            if plan.collection_type == TripPlan.COLLECTION_TYPE_BIN:
                cps = Collection_point.objects.filter(is_deleted=False, is_active=True)
                for field in HIERARCHY_FIELDS:
                    value = hierarchy.get(field)
                    if value:
                        cps = cps.filter(**{field: value})
                        break
                cps = cps.order_by("cp_name")

                for cp in cps:
                    bin_obj = Bins.objects.filter(
                        collection_point_id=cp,
                        wastetype_id=plan.waste_type_id,
                        is_deleted=False,
                        is_active=True,
                    ).first()
                    if not bin_obj:
                        continue

                    sequence += 1
                    _, created = TripPlanCollectionPoint.objects.update_or_create(
                        trip_plan_id=plan,
                        collection_type=TripPlanCollectionPoint.COLLECTION_TYPE_BIN,
                        collection_point_id=cp,
                        defaults={
                            "bin_id": bin_obj,
                            "sequence": sequence,
                            "is_active": True,
                            "is_deleted": False,
                        },
                    )
                    if created:
                        total_created += 1

            elif plan.collection_type in {
                TripPlan.COLLECTION_TYPE_HOUSEHOLD,
                TripPlan.COLLECTION_TYPE_BULK,
            }:
                sequence += 1
                _, created = TripPlanCollectionPoint.objects.update_or_create(
                    trip_plan_id=plan,
                    collection_type=plan.collection_type,
                    customer_id=None,
                    defaults={
                        # Both TripPlan and TripPlanCollectionPoint now carry a
                        # single location_node instead of per-hierarchy FKs.
                        "location_node": plan.location_node,
                        "sequence": sequence,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if created:
                    total_created += 1

        self.log(f"---TripPlanCollectionPoint seeded | created={total_created}---")
