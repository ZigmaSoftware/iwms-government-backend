from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class ProjectSeeder(BaseSeeder):
    name = "project"

    def run(self):
        companies = Company.objects.filter(is_deleted=False).exclude(name__iexact="Blue Planet")
        if not companies.exists():
            self.log("No companies found. Skipping project seeding.")
            return

        created = 0
        updated = 0

        for company in companies:
            project_name = f"{company.name} Main Project"
            project, was_created = Project.objects.get_or_create(
                name=project_name,
                company_id=company,
                defaults={
                    "description": f"Default project for {company.name}",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if was_created:
                created += 1
            else:
                project.description = f"Default project for {company.name}"
                project.is_active = True
                project.is_deleted = False
                project.save(update_fields=["description", "is_active", "is_deleted"])
                updated += 1

        self.log(f"---Projects seeded | Created: {created}, Updated: {updated}---")
