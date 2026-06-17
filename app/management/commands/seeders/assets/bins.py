from app.management.commands.seeders.base import BaseSeeder


class BinSeeder(BaseSeeder):
    name = "BinSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
