from app.management.commands.seeders.base import BaseSeeder


class CitySeeder(BaseSeeder):
    name = "CitySeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
