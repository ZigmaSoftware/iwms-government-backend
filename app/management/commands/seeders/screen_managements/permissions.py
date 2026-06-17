from app.management.commands.seeders.base import BaseSeeder


class PermissionSeeder(BaseSeeder):
    name = "PermissionSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
