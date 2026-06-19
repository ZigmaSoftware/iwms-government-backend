from app.management.commands.seeders.base import BaseSeeder


class BinCollectionEventSeeder(BaseSeeder):
    name = "BinCollectionEventSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
