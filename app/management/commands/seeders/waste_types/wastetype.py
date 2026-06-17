from app.management.commands.seeders.base import BaseSeeder


class WasteTypeSeeder(BaseSeeder):
    name = "WasteTypeSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
