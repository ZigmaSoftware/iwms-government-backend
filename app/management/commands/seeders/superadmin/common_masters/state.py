from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State


class StateSeeder(BaseSeeder):
    """Bug fix: the old seeder passed a `coordinates` kwarg that State has
    no field for — harmless on update, but raises FieldError on a fresh
    database's create path (see ContinentSeeder)."""

    name = "state"

    # (state_name, label)
    STATES = [
        ("Tamil Nadu", "TN"),
        ("Karnataka", "KA"),
        ("Kerala", "KL"),
        ("Andhra Pradesh", "AP"),
        ("Telangana", "TS"),
    ]

    def run(self):
        asia = self.pick_existing(Continent, name="Asia")
        india = self.pick_existing(Country, name="India")

        for name, label in self.STATES:
            self.upsert(
                State,
                name=name,
                country_id=india.unique_id,
                continent_id=asia.unique_id,
                defaults={
                    "label": label,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        self.log(f"---States seeded ({len(self.STATES)} records)---")
