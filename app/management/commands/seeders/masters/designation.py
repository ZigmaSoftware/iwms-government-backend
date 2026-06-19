from app.management.commands.seeders.base import BaseSeeder


class DesignationSeeder(BaseSeeder):
    name = "DesignationSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
