from decimal import Decimal

from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.collection_point import Collection_point


class CollectionPointSeeder(BaseSeeder):
    name = "CollectionPointSeeder"

    # (cp_name, panchayat_name, latitude, longitude)
    COLLECTION_POINTS = [
        ("CP-Anthiyur-01",      "Anthiyur Panchayat",         Decimal("11.3410"), Decimal("77.5820")),
        ("CP-Bhavani-01",       "Bhavani Panchayat",          Decimal("11.4437"), Decimal("77.6845")),
        ("CP-Gobichettipalayam","Gobichettipalayam Panchayat", Decimal("11.4524"), Decimal("77.4355")),
        ("CP-Kavundampalayam",  "Kavundampalayam Panchayat",  Decimal("11.2932"), Decimal("77.6011")),
        ("CP-Modakkurichi",     "Modakkurichi Panchayat",     Decimal("11.3805"), Decimal("77.7032")),
    ]

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        district = District.objects.filter(name="Erode", state_id=tamil_nadu).first()

        if not tamil_nadu or not district:
            self.log("Tamil Nadu / Erode not found — run StateSeeder and DistrictSeeder first.")
            return

        count = 0
        for cp_name, panchayat_name, lat, lon in self.COLLECTION_POINTS:
            panchayat = Panchayat.objects.filter(
                panchayat_name=panchayat_name, district_id=district
            ).first()
            if not panchayat:
                self.log(f"Panchayat '{panchayat_name}' not found — skipping.")
                continue

            _, created = Collection_point.objects.get_or_create(
                cp_name=cp_name,
                district_id=district,
                defaults={
                    "state_id": tamil_nadu,
                    "panchayat_id": panchayat,
                    "latitude": lat,
                    "longitude": lon,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                count += 1

        self.log(f"---Collection points seeded ({count} created)---")
