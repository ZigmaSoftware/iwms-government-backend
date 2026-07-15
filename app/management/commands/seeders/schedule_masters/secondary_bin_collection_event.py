from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins
from app.models.schedule_masters.secondary_bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint


class BinCollectionEventSeeder(BaseSeeder):
    name = "BinCollectionEventSeeder"

    def run(self):
        trip_cps = list(
            DailyTripCollectionPoint.objects.filter(is_deleted=False)
            .select_related(
                "trip_assignment_id",
                "collection_point_id",
                "bin_id",
                "bin_id__wastetype_id",
            )
            .order_by("-trip_assignment_id__trip_date")[:5]
        )

        if not trip_cps:
            self.log("No DailyTripCollectionPoints found — run DailyTripCollectionPointSeeder first.")
            return

        status_cycle = [
            (BinCollectionEvent.STATUS_COLLECTED, ""),
            (BinCollectionEvent.STATUS_NOT_COLLECTED, "I do not collect today: bin was inaccessible."),
            (BinCollectionEvent.STATUS_COLLECT_LATER, "I will collect today after route clearance."),
        ]
        count = 0
        for idx, tcp in enumerate(trip_cps):
            if not tcp.bin_id or not tcp.collection_point_id:
                continue

            already_exists = BinCollectionEvent.objects.filter(
                trip_assignment_id=tcp.trip_assignment_id,
                trip_collection_point_id=tcp,
                bin_id=tcp.bin_id,
                is_deleted=False,
            ).exists()
            if already_exists:
                continue

            weight = Decimal("50.00") + (Decimal(idx) * Decimal("10.00"))
            collection_date = (timezone.localdate() - timedelta(days=idx))
            status, status_reason = status_cycle[idx % len(status_cycle)]

            BinCollectionEvent.objects.create(
                trip_assignment_id=tcp.trip_assignment_id,
                trip_collection_point_id=tcp,
                collection_point_id=tcp.collection_point_id,
                bin_id=tcp.bin_id,
                waste_type_id=tcp.bin_id.wastetype_id,
                vehicle_id=tcp.trip_assignment_id.vehicle_id,
                collected_weight_kg=weight if status == BinCollectionEvent.STATUS_COLLECTED else None,
                status=status,
                status_reason=status_reason,
                collection_date=collection_date,
                driver_latitude=Decimal("11.341"),
                driver_longitude=Decimal("77.717"),
                notes=f"Seeder bin collection event {idx + 1}",
                is_active=True,
                is_deleted=False,
            )
            count += 1

        examples = list(
            BinCollectionEvent.objects.filter(is_deleted=False)
            .order_by("-created_at")[:6]
        )
        updated_count = 0
        for idx, event in enumerate(examples):
            status, status_reason = status_cycle[idx % len(status_cycle)]
            event.status = status
            event.status_reason = status_reason
            if status != BinCollectionEvent.STATUS_COLLECTED:
                event.collected_weight_kg = None
            elif event.collected_weight_kg is None:
                event.collected_weight_kg = Decimal("50.00")
            event.save(update_fields=[
                "status",
                "status_reason",
                "collected_weight_kg",
                "updated_at",
            ])
            updated_count += 1

        self.log(f"---Bin collection events seeded ({count} created, {updated_count} examples updated)---")
