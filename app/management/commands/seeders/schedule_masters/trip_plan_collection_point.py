from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)


class TripPlanCollectionPointSeeder(BaseSeeder):
    name = "trip_plan_collection_point"

    def run(self):
        total_created = 0
        plans = TripPlan.objects.filter(is_deleted=False, status=TripPlan.Status.ACTIVE)

        for plan in plans:
            cps = Collection_point.objects.filter(is_deleted=False)
            if plan.panchayat_id:
                cps = cps.filter(panchayat_id=plan.panchayat_id)
            elif plan.ward_id:
                cps = cps.filter(ward_id=plan.ward_id)
            cps = cps.order_by("cp_name")

            sequence = 0
            for cp in cps:
                bin_obj = Bins.objects.filter(
                    collection_point_id=cp,
                    wastetype_id=plan.waste_type_id,
                    is_deleted=False,
                ).first()
                if not bin_obj:
                    bin_obj = Bins.objects.filter(
                        collection_point_id=cp,
                        is_deleted=False,
                    ).first()
                if not bin_obj:
                    continue

                sequence += 1
                _, created = TripPlanCollectionPoint.objects.get_or_create(
                    trip_plan_id=plan,
                    collection_point_id=cp,
                    defaults={
                        "bin_id": bin_obj,
                        "sequence": sequence,
                        "is_active": True,
                    },
                )
                if created:
                    total_created += 1

        self.log(f"---TripPlanCollectionPoint seeded | created={total_created}---")
