from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.common_masters.continent import Continent


class ContinentSeeder(BaseSeeder):
    name = "continent"

    CONTINENTS = [
        "Asia",
        "Europe",
        "Africa",
        "North America",
        "South America",
    ]

    def run(self):
        for name in self.CONTINENTS:
            Continent.objects.update_or_create(
                name=name,
                defaults={"is_active": True, "is_deleted": False},
            )

        self.log(f"---Continents seeded ({len(self.CONTINENTS)} records)---")
