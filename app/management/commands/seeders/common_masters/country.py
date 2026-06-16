# seeders/masters/country.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country


class CountrySeeder(BaseSeeder):
    name = "country"

    # (country_name, continent_name)
    COUNTRIES = [
        ("India",       "Asia"),
        ("China",       "East Asia"),
        ("Japan",       "East Asia"),
        ("Bangladesh",  "South Asia"),
        ("Pakistan",    "South Asia"),
        ("Sri Lanka",   "South Asia"),
        ("Nepal",       "South Asia"),
        ("Myanmar",     "Southeast Asia"),
        ("Thailand",    "Southeast Asia"),
        ("Vietnam",     "Southeast Asia"),
        ("Malaysia",    "Southeast Asia"),
        ("Indonesia",   "Southeast Asia"),
        ("Philippines", "Southeast Asia"),
        ("Singapore",   "Southeast Asia"),
        ("South Korea", "East Asia"),
    ]

    def run(self):
        continent_cache = {}
        for country_name, continent_name in self.COUNTRIES:
            if continent_name not in continent_cache:
                continent_cache[continent_name] = Continent.objects.get(name=continent_name)
            Country.objects.get_or_create(
                name=country_name,
                continent_id=continent_cache[continent_name],
            )

        self.log(f"---Countries seeded ({len(self.COUNTRIES)} records)---")
