from app.management.commands.seeders.base import BaseSeeder


class PlatformDeveloperSeeder(BaseSeeder):
    name = "PlatformDeveloperSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
