from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District
from app.models.masters.municipality import Municipality


class MunicipalitySeeder(BaseSeeder):
    name = "MunicipalitySeeder"

    MUNICIPALITIES = [
        ("Erode", "Bhavani Municipality", coordinates((11.4437, 77.6845), (11.4550, 77.6720))),
        ("Salem", "Attur Municipality", coordinates((11.5941, 78.6014), (11.6070, 78.5960))),
        ("Coimbatore", "Pollachi Municipality", coordinates((10.6587, 77.0085), (10.6700, 77.0150))),
        ("Chennai", "Avadi Municipality", coordinates((13.1143, 80.1098), (13.1260, 80.1010))),
        ("Madurai", "Melur Municipality", coordinates((10.0329, 78.3396), (10.0450, 78.3310))),
    ]

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        if not tamil_nadu:
            self.log("Tamil Nadu state not found — run StateSeeder first.")
            return

        count = 0
        for district_name, municipality_name, geo_coordinates in self.MUNICIPALITIES:
            district = District.objects.filter(state_id=tamil_nadu, name=district_name).first()
            area_type = AreaType.objects.filter(
                state_id=tamil_nadu,
                district_id=district,
                name="Urban Local Body",
            ).first()
            if not district or not area_type:
                self.log(f"Urban area type for '{district_name}' not found — skipping.")
                continue

            Municipality.objects.update_or_create(
                state_id=tamil_nadu,
                district_id=district,
                area_type_id=area_type,
                municipality_name=municipality_name,
                defaults={
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            count += 1

        self.log(f"---Municipalities seeded ({count} records)---")
