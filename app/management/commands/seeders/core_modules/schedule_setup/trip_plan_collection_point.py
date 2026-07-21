from django.db.models import Max

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)


FLAT_HIERARCHY_FIELDS = (
    "panchayat",
    "panchayat_union",
    "town_panchayat",
    "municipality",
    "corporation",
    "area_type",
    "district",
    "state",
)


class TripPlanCollectionPointSeeder(BaseSeeder):
    name = "trip_plan_collection_point"

    def run(self):
        total_created = 0
        plans = TripPlan.objects.filter(is_deleted=False, status=TripPlan.Status.ACTIVE)

        for plan in plans:
            # The DB enforces UNIQUE(trip_plan, sequence) across ALL rows (MariaDB
            # cannot make it conditional), while update_or_create below looks rows
            # up by collection keys — not by sequence. So before assigning fresh
            # 1..N sequences, park every existing stop of this plan at a range
            # guaranteed to be free (above the plan's current max), otherwise a
            # re-seed after collection points/bins changed collides on sequence.
            all_stops = TripPlanCollectionPoint.objects.filter(trip_plan_id=plan)
            max_seq = all_stops.aggregate(m=Max("sequence"))["m"] or 0
            park_base = max(max_seq, 9000)
            offset = 0

            stale_stops = all_stops.exclude(
                collection_type=plan.collection_type,
            ).order_by("sequence", "unique_id")
            for stop in stale_stops:
                offset += 1
                stop.sequence = park_base + offset
                stop.is_active = False
                stop.is_deleted = True
                stop.save(update_fields=["sequence", "is_active", "is_deleted", "updated_at"])

            same_type_stops = all_stops.filter(
                collection_type=plan.collection_type,
            ).order_by("sequence", "unique_id")
            for stop in same_type_stops:
                offset += 1
                stop.sequence = park_base + offset
                stop.save(update_fields=["sequence", "updated_at"])

            sequence = 0

            if plan.collection_type == TripPlan.COLLECTION_TYPE_BIN:
                cps = Collection_point.objects.filter(is_deleted=False, is_active=True)
                for field in FLAT_HIERARCHY_FIELDS:
                    value = getattr(plan, field, None)
                    if value:
                        cps = cps.filter(**{field: value})
                        break
                cps = cps.order_by("cp_name")

                for cp in cps:
                    bin_obj = Bins.objects.filter(
                        collection_point_id=cp,
                        wastetype_id__in=plan.waste_types.all(),
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
                # location_node is auto-copied from trip_plan_id in
                # TripPlanCollectionPoint.save() — no need to set it here.
                _, created = TripPlanCollectionPoint.objects.update_or_create(
                    trip_plan_id=plan,
                    collection_type=plan.collection_type,
                    customer_id=None,
                    defaults={
                        # Geo hierarchy is auto-copied from trip_plan_id in
                        # TripPlanCollectionPoint.save() (copy_flat_geo) — no need to set it here.
                        "sequence": sequence,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if created:
                    total_created += 1

        self.log(f"---TripPlanCollectionPoint seeded | created={total_created}---")
