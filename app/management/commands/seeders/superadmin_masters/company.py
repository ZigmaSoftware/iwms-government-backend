# api/management/commands/seeders/company_seeder.py

from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin_masters.company import Company


class CompanySeeder(BaseSeeder):
    name = "company"

    def run(self):
        companies = [
            ("IWMS", "Integrated Waste Management System"),
            ("SmartCity Corp", "Smart city platform"),
        ]

        for name, desc in companies:
            Company.objects.get_or_create(
                name=name,
                defaults={
                    "description": desc,
                    "is_active": True,
                    "is_deleted": False,
                }
            )

        self.log("---Companies seeded---")
