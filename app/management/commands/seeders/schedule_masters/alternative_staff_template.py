from app.management.commands.seeders.base import BaseSeeder


class AlternativeStaffTemplateSeeder(BaseSeeder):
    name = "AlternativeStaffTemplateSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
