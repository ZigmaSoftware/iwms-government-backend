from app.management.commands.seeders.base import BaseSeeder


class ProjectSeeder(BaseSeeder):
    name = "ProjectSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
