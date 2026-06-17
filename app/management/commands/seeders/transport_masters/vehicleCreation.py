from app.management.commands.seeders.base import BaseSeeder


class VehicleCreationSeeder(BaseSeeder):
    name = "VehicleCreationSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
