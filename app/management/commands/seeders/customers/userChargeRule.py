from app.management.commands.seeders.base import BaseSeeder


class UserChargeRuleSeeder(BaseSeeder):
    name = "UserChargeRuleSeeder"

    def run(self):
        self.log("Skipped: Company/Project tenancy has been removed.")
