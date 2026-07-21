from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.superadmin.common_masters.continent import Continent


class ContinentSeeder(BaseSeeder):
    name = "continent"

    CONTINENTS = [
        ("Asia", coordinates((34.0479, 100.6197), (20.5937, 78.9629))),
        ("Europe", coordinates((54.5260, 15.2551), (48.8566, 2.3522))),
        ("Africa", coordinates((-8.7832, 34.5085), (9.0820, 8.6753))),
        ("North America", coordinates((54.5260, -105.2551), (37.0902, -95.7129))),
        ("South America", coordinates((-8.7832, -55.4915), (-14.2350, -51.9253))),
    ]

    def run(self):
        for name, geo_coordinates in self.CONTINENTS:
            Continent.objects.update_or_create(
                name=name,
                defaults={"coordinates": geo_coordinates, "is_active": True, "is_deleted": False},
            )

        self.log(f"---Continents seeded ({len(self.CONTINENTS)} records)---")
