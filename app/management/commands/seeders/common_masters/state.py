from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State


class StateSeeder(BaseSeeder):
    name = "state"

    # (state_name, label)
    STATES = [
        ("Tamil Nadu",     "TN"),
        ("Karnataka",      "KA"),
        ("Kerala",         "KL"),
        ("Andhra Pradesh", "AP"),
        ("Telangana",      "TS"),
    ]

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")

        for name, label in self.STATES:
            State.objects.get_or_create(
                name=name,
                country_id=india,
                continent_id=asia,
                defaults={"label": label},
            )

        self.log(f"---States seeded ({len(self.STATES)} records)---")
