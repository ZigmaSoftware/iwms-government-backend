from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District


class AreaTypeSeeder(BaseSeeder):
    name = "AreaTypeSeeder"

    # (district_name, area_type_name, coordinates)
    AREA_TYPE_ASSIGNMENTS = [
        ("Erode", "Urban Local Body", coordinates((11.3410, 77.7172), (11.3690, 77.6760))),
        ("Erode", "Rural Local Body", coordinates((11.2932, 77.6011), (11.3805, 77.7032))),
        ("Salem", "Urban Local Body", coordinates((11.6643, 78.1460), (11.6740, 78.1350))),
        ("Salem", "Rural Local Body", coordinates((11.6200, 78.0900), (11.7100, 78.2100))),
        ("Coimbatore", "Urban Local Body", coordinates((11.0168, 76.9558), (11.0046, 76.9616))),
        ("Coimbatore", "Rural Local Body", coordinates((10.9900, 76.9100), (11.0500, 76.8800))),
        ("Chennai", "Urban Local Body", coordinates((13.0827, 80.2707), (13.0674, 80.2376))),
        ("Chennai", "Rural Local Body", coordinates((13.1600, 80.1900), (13.2100, 80.1200))),
        ("Madurai", "Urban Local Body", coordinates((9.9252, 78.1198), (9.9195, 78.1210))),
        ("Madurai", "Rural Local Body", coordinates((9.8600, 78.0500), (9.9900, 78.1800))),
    ]

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        if not tamil_nadu:
            self.log("Tamil Nadu state not found — run StateSeeder first.")
            return

        count = 0
        for district_name, area_type_name, geo_coordinates in self.AREA_TYPE_ASSIGNMENTS:
            district = District.objects.filter(state_id=tamil_nadu, name=district_name).first()
            if not district:
                self.log(f"District '{district_name}' not found — skipping.")
                continue

            AreaType.objects.update_or_create(
                state_id=tamil_nadu,
                district_id=district,
                name=area_type_name,
                defaults={
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            count += 1

        self.log(f"---Area types seeded ({count} records)---")
