from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District
from app.models.masters.panchayat_union import PanchayatUnion


class PanchayatUnionSeeder(BaseSeeder):
    name = "PanchayatUnionSeeder"

    PANCHAYAT_UNIONS = [
        ("Erode", "Anthiyur Panchayat Union", coordinates((11.5750, 77.5900), (11.5660, 77.6040))),
        ("Erode", "Bhavani Panchayat Union", coordinates((11.4437, 77.6845), (11.4550, 77.6720))),
        ("Salem", "Omalur Panchayat Union", coordinates((11.7400, 78.0450), (11.7520, 78.0550))),
        ("Coimbatore", "Pollachi Panchayat Union", coordinates((10.6587, 77.0085), (10.6700, 77.0150))),
        ("Madurai", "Melur Panchayat Union", coordinates((10.0329, 78.3396), (10.0450, 78.3310))),
    ]

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        if not tamil_nadu:
            self.log("Tamil Nadu state not found — run StateSeeder first.")
            return

        count = 0
        for district_name, union_name, geo_coordinates in self.PANCHAYAT_UNIONS:
            district = District.objects.filter(state_id=tamil_nadu, name=district_name).first()
            area_type = AreaType.objects.filter(
                state_id=tamil_nadu,
                district_id=district,
                name="Rural Local Body",
            ).first()
            if not district or not area_type:
                self.log(f"Rural area type for '{district_name}' not found — skipping.")
                continue

            PanchayatUnion.objects.update_or_create(
                state_id=tamil_nadu,
                district_id=district,
                area_type_id=area_type,
                union_name=union_name,
                defaults={
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            count += 1

        self.log(f"---Panchayat unions seeded ({count} records)---")
