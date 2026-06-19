from app.management.commands.seeders.base import BaseSeeder


class StaffOfficeSeeder(BaseSeeder):
    name = "StaffOfficeSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
