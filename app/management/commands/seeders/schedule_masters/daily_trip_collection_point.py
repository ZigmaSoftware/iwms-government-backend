from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)


class DailyTripCollectionPointSeeder(BaseSeeder):
    name = "daily_trip_collection_point"

    def run(self):
        today = timezone.localdate()
        assignments = (
            DailyTripAssignment.objects
            .filter(trip_date=today, is_deleted=False)
            .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
            .select_related("panchayat_id", "waste_type_id")
        )

        if not assignments.exists():
            assignments = (
                DailyTripAssignment.objects
                .filter(is_deleted=False)
                .exclude(status=DailyTripAssignment.STATUS_CANCELLED)
                .select_related("panchayat_id", "waste_type_id")
                .order_by("-trip_date", "-scheduled_time")[:3]
            )

        if not assignments:
            self.log("No DailyTripAssignment found — skipping.")
            return

        total_created = 0
        for assignment in assignments:
            cp_qs = Collection_point.objects.filter(is_deleted=False)
            if assignment.panchayat_id:
                cp_qs = cp_qs.filter(panchayat_id=assignment.panchayat_id)
            cps = list(cp_qs.order_by("cp_name"))

            if not cps:
                cps = list(
                    Collection_point.objects
                    .filter(is_deleted=False)
                    .order_by("cp_name")[:5]
                )

            sequence = 0
            for cp in cps:
                bin_obj = Bins.objects.filter(
                    collection_point_id=cp,
                    wastetype_id=assignment.waste_type_id,
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
                _, created = DailyTripCollectionPoint.objects.get_or_create(
                    trip_assignment_id=assignment,
                    collection_point_id=cp,
                    defaults={
                        "bin_id": bin_obj,
                        "sequence": sequence,
                        "is_collected": False,
                        "status": DailyTripCollectionPoint.STATUS_PENDING,
                    },
                )
                if created:
                    total_created += 1

        self.log(
            f"---DailyTripCollectionPoint seeded | created={total_created}---"
        )
