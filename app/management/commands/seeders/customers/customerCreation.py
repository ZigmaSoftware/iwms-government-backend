from app.management.commands.seeders.base import BaseSeeder


class CustomerCreationSeeder(BaseSeeder):
    name = "CustomerCreationSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
