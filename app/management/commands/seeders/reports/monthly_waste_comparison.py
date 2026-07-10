from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.daily_waste_comparison import DailyWasteComparison
from app.models.user_creations.waste_collection_bluetooth import WasteType


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

            agreed = Decimal("500.00") + (Decimal(idx) * Decimal("50.00"))
            actual = agreed - (Decimal("20.00") * Decimal(idx + 1))
            variance = agreed - actual
            variance_pct = (variance / agreed * 100).quantize(Decimal("0.01"))

            DailyWasteComparison.objects.create(
                panchayat=panchayat,
                district=panchayat.district_id,
                state=panchayat.state_id,
                area_type=panchayat.area_type_id,
                collection_date=collection_date,
                waste_type_id=waste_type,
                agreed_weight_kg=agreed,
                actual_weight_kg=actual,
                variance_kg=variance,
                variance_percent=variance_pct,
                report_status="Verified",
                total_trips=2 + idx,
                collection_points_covered=3 + idx,
            )
            count += 1

        self.log(f"---Daily waste comparison records seeded ({count} created)---")
