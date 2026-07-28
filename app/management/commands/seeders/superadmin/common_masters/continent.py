from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.common_masters.continent import Continent


class ContinentSeeder(BaseSeeder):
    """Bug fix: the old seeder passed a `coordinates` kwarg that the
    Continent model has no field for — Django only tolerates that silently
    on the update path (setattr on an existing instance); on a fresh/empty
    database (the create path) it raises FieldError immediately, so a
    from-scratch `manage.py seed` could never complete."""

    name = "continent"

    CONTINENTS = ["Asia", "Europe", "Africa", "North America", "South America"]

    def run(self):
        for name in self.CONTINENTS:
            Continent.objects.update_or_create(
                name=name,
                defaults={"is_active": True, "is_deleted": False},
            )

        self.log(f"---Continents seeded ({len(self.CONTINENTS)} records)---")
