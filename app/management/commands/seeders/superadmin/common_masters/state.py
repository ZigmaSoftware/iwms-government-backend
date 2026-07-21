from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State


class StateSeeder(BaseSeeder):
    name = "state"

    # (state_name, label, coordinates)
    STATES = [
        ("Tamil Nadu", "TN", coordinates((11.1271, 78.6569), (13.0827, 80.2707), (11.3410, 77.7172))),
        ("Karnataka", "KA", coordinates((15.3173, 75.7139), (12.9716, 77.5946))),
        ("Kerala", "KL", coordinates((10.8505, 76.2711), (8.5241, 76.9366))),
        ("Andhra Pradesh", "AP", coordinates((15.9129, 79.7400), (16.5062, 80.6480))),
        ("Telangana", "TS", coordinates((18.1124, 79.0193), (17.3850, 78.4867))),
    ]

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")

        for name, label, geo_coordinates in self.STATES:
            State.objects.update_or_create(
                name=name,
                country_id=india,
                continent_id=asia,
                defaults={
                    "label": label,
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        self.log(f"---States seeded ({len(self.STATES)} records)---")
