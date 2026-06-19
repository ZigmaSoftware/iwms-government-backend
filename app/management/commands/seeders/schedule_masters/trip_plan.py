from app.management.commands.seeders.base import BaseSeeder


class TripPlanSeeder(BaseSeeder):
    name = "TripPlanSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
