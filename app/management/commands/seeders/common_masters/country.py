from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country


class CountrySeeder(BaseSeeder):
    name = "country"

    # (country_name, continent_name, currency, mob_code, coordinates)
    COUNTRIES = [
        ("India", "Asia", "INR", "+91", coordinates((20.5937, 78.9629), (28.6139, 77.2090))),
        ("United States", "North America", "USD", "+1", coordinates((37.0902, -95.7129), (38.9072, -77.0369))),
        ("Germany", "Europe", "EUR", "+49", coordinates((51.1657, 10.4515), (52.5200, 13.4050))),
        ("Nigeria", "Africa", "NGN", "+234", coordinates((9.0820, 8.6753), (9.0765, 7.3986))),
        ("Brazil", "South America", "BRL", "+55", coordinates((-14.2350, -51.9253), (-15.7939, -47.8828))),
    ]

    def run(self):
        continent_cache = {}
        for country_name, continent_name, currency, mob_code, geo_coordinates in self.COUNTRIES:
            if continent_name not in continent_cache:
                continent_cache[continent_name] = Continent.objects.get(name=continent_name)
            Country.objects.update_or_create(
                name=country_name,
                continent_id=continent_cache[continent_name],
                defaults={
                    "currency": currency,
                    "mob_code": mob_code,
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        self.log(f"---Countries seeded ({len(self.COUNTRIES)} records)---")
