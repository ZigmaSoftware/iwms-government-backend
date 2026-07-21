from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.district import District


class CorporationSeeder(BaseSeeder):
    name = "CorporationSeeder"

    CORPORATIONS = [
        ("Erode", "Erode Corporation", coordinates((11.3410, 77.7172), (11.3690, 77.6760))),
        ("Salem", "Salem Corporation", coordinates((11.6643, 78.1460), (11.6740, 78.1350))),
        ("Coimbatore", "Coimbatore Corporation", coordinates((11.0168, 76.9558), (11.0046, 76.9616))),
        ("Chennai", "Greater Chennai Corporation", coordinates((13.0827, 80.2707), (13.0674, 80.2376))),
        ("Madurai", "Madurai Corporation", coordinates((9.9252, 78.1198), (9.9195, 78.1210))),
    ]

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        if not tamil_nadu:
            self.log("Tamil Nadu state not found — run StateSeeder first.")
            return

        count = 0
        for district_name, corporation_name, geo_coordinates in self.CORPORATIONS:
            district = District.objects.filter(state_id=tamil_nadu, name=district_name).first()
            area_type = AreaType.objects.filter(
                state_id=tamil_nadu,
                district_id=district,
                name="Urban Local Body",
            ).first()
            if not district or not area_type:
                self.log(f"Urban area type for '{district_name}' not found — skipping.")
                continue

            Corporation.objects.update_or_create(
                state_id=tamil_nadu,
                district_id=district,
                area_type_id=area_type,
                corporation_name=corporation_name,
                defaults={
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            count += 1

        self.log(f"---Corporations seeded ({count} records)---")
