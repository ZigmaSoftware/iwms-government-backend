from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District
from app.models.masters.town_panchayat import TownPanchayat


class TownPanchayatSeeder(BaseSeeder):
    name = "TownPanchayatSeeder"

    TOWN_PANCHAYATS = [
        ("Erode", "Anthiyur Town Panchayat", coordinates((11.5750, 77.5900), (11.5660, 77.6040))),
        ("Salem", "Vazhapadi Town Panchayat", coordinates((11.6550, 78.3990), (11.6660, 78.4100))),
        ("Coimbatore", "Periyanaickenpalayam Town Panchayat", coordinates((11.1520, 76.9490), (11.1650, 76.9550))),
        ("Chennai", "Minjur Town Panchayat", coordinates((13.2790, 80.2580), (13.2860, 80.2700))),
        ("Madurai", "Alanganallur Town Panchayat", coordinates((10.0460, 78.0900), (10.0550, 78.1010))),
    ]

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        if not tamil_nadu:
            self.log("Tamil Nadu state not found — run StateSeeder first.")
            return

        count = 0
        for district_name, town_panchayat_name, geo_coordinates in self.TOWN_PANCHAYATS:
            district = District.objects.filter(state_id=tamil_nadu, name=district_name).first()
            area_type = AreaType.objects.filter(
                state_id=tamil_nadu,
                district_id=district,
                name="Urban Local Body",
            ).first()
            if not district or not area_type:
                self.log(f"Urban area type for '{district_name}' not found — skipping.")
                continue

            TownPanchayat.objects.update_or_create(
                state_id=tamil_nadu,
                district_id=district,
                area_type_id=area_type,
                town_panchayat_name=town_panchayat_name,
                defaults={
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            count += 1

        self.log(f"---Town panchayats seeded ({count} records)---")
