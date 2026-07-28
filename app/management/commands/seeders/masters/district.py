from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District


class DistrictSeeder(BaseSeeder):
    name = "DistrictSeeder"
    DISTRICTS = [
        ("Erode", "ERD", coordinates((11.3410, 77.7172), (11.3690, 77.6760), (11.2750, 77.5870))),
        ("Salem", "SLM", coordinates((11.6643, 78.1460), (11.6740, 78.1350), (11.6460, 78.1620))),
        ("Coimbatore", "CBE", coordinates((11.0168, 76.9558), (11.0046, 76.9616), (11.0500, 76.9400))),
        ("Chennai", "CHN", coordinates((13.0827, 80.2707), (13.0674, 80.2376), (13.1067, 80.2865))),
        ("Madurai", "MDU", coordinates((9.9252, 78.1198), (9.9195, 78.1210), (9.9400, 78.0900))),
    ]

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(name="Tamil Nadu", country_id=india, continent_id=asia)

        for name, code, geo_coordinates in self.DISTRICTS:
            District.objects.update_or_create(
                state_id=tamil_nadu,
                name=name,
                defaults={
                    "continent_id": asia,
                    "country_id": india,
                    "district_code": code,
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        self.log(f"Districts seeded ({len(self.DISTRICTS)} Tamil Nadu records).")
