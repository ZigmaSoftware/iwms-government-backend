from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District


class DistrictSeeder(BaseSeeder):
    name = "DistrictSeeder"
    DISTRICTS = [
        ("Erode", "ERD"),
        ("Salem", "SLM"),
        ("Coimbatore", "CBE"),
        ("Chennai", "CHN"),
        ("Madurai", "MDU"),
    ]

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(name="Tamil Nadu", country_id=india, continent_id=asia)

        for name, code in self.DISTRICTS:
            District.objects.update_or_create(
                state_id=tamil_nadu,
                name=name,
                defaults={
                    "continent_id": asia,
                    "country_id": india,
                    "district_code": code,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        self.log(f"Districts seeded ({len(self.DISTRICTS)} Tamil Nadu records).")
