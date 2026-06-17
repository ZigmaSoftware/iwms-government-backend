from app.management.commands.seeders.base import BaseSeeder


class AreaTypeSeeder(BaseSeeder):
    name = "AreaTypeSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
