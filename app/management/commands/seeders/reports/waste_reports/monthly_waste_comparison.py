from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.panchayat import Panchayat
from app.models.reports.waste_reports.daily_waste_comparison import DailyWasteComparison
from app.models.masters.waste_masters.wastetype import WasteType


class MonthlyWasteComparisonSeeder(BaseSeeder):
    name = "MonthlyWasteComparisonSeeder"

    def run(self):
        panchayats = list(Panchayat.objects.filter(is_deleted=False).order_by("panchayat_name")[:5])
        if not panchayats:
            self.log("No panchayats found — run PanchayatSeeder first.")
            return

        waste_type = WasteType.objects.filter(
            waste_type_name="Organic Waste", is_deleted=False
        ).first()
        if not waste_type:
            self.log("WasteType 'Organic Waste' not found — run WasteTypeSeeder first.")
            return

        today = timezone.localdate()
        count = 0
        for idx, panchayat in enumerate(panchayats):
            collection_date = today - timedelta(days=idx)

            already_exists = DailyWasteComparison.objects.filter(
                panchayat=panchayat,
                collection_date=collection_date,
                waste_type_id=waste_type,
            ).exists()
            if already_exists:
                self.log(f"Record for '{panchayat.panchayat_name}' on {collection_date} exists — skipping.")
                continue

            actual = Decimal("480.00") - (Decimal("20.00") * Decimal(idx))

            DailyWasteComparison.objects.create(
                panchayat=panchayat,
                district=panchayat.district_id,
                state=panchayat.state_id,
                area_type=panchayat.area_type_id,
                collection_date=collection_date,
                waste_type_id=waste_type,
                actual_weight_kg=actual,
                total_trips=2 + idx,
                collection_points_covered=3 + idx,
            )
            count += 1

        self.log(f"---Daily waste comparison records seeded ({count} created)---")
