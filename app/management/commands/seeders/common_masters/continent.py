# seeders/masters/continent.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent


class ContinentSeeder(BaseSeeder):
    name = "continent"

    CONTINENTS = [
        "Asia",
        "Europe",
        "Africa",
        "North America",
        "South America",
        "Australia",
        "Antarctica",
        "Middle East",
        "Central Asia",
        "Southeast Asia",
        "East Asia",
        "South Asia",
        "Caribbean",
        "Pacific Islands",
        "Arctic",
    ]

    def run(self):
        for name in self.CONTINENTS:
            Continent.objects.get_or_create(name=name)

        self.log(f"---Continents seeded ({len(self.CONTINENTS)} records)---")
