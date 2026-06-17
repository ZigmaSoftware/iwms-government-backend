from app.management.commands.seeders.base import BaseSeeder


class WeighbridgeCheckSeeder(BaseSeeder):
    name = "WeighbridgeCheckSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
