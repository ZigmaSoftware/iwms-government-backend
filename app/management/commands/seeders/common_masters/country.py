from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country


class CountrySeeder(BaseSeeder):
    name = "country"

    # (country_name, continent_name, currency, mob_code)
    COUNTRIES = [
        ("India",          "Asia",          "INR", "+91"),
        ("United States",  "North America", "USD", "+1"),
        ("Germany",        "Europe",        "EUR", "+49"),
        ("Nigeria",        "Africa",        "NGN", "+234"),
        ("Brazil",         "South America", "BRL", "+55"),
    ]

    def run(self):
        continent_cache = {}
        for country_name, continent_name, currency, mob_code in self.COUNTRIES:
            if continent_name not in continent_cache:
                continent_cache[continent_name] = Continent.objects.get(name=continent_name)
            Country.objects.get_or_create(
                name=country_name,
                continent_id=continent_cache[continent_name],
                defaults={"currency": currency, "mob_code": mob_code},
            )

        self.log(f"---Countries seeded ({len(self.COUNTRIES)} records)---")
