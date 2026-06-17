from app.management.commands.seeders.base import BaseSeeder


class MonthlyWasteComparisonSeeder(BaseSeeder):
    name = "MonthlyWasteComparisonSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
