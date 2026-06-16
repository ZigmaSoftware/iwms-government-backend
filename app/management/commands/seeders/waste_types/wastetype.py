from app.management.commands.seeders.base import BaseSeeder
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class WasteTypeSeeder(BaseSeeder):
    name = "waste_type"

    WASTE_TYPES = [
        "Organic Waste",
        "Plastic Waste",
        "Dry Waste",
        "Wet Waste",
        "Electronic Waste",
        "Hazardous Waste",
        "Medical Waste",
        "Construction Waste",
        "Green Waste",
        "Metal Waste",
        "Glass Waste",
        "Paper Waste",
        "Textile Waste",
        "Food Waste",
        "Chemical Waste",
    ]

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        for wt in self.WASTE_TYPES:
            _, created = WasteType.objects.update_or_create(
                waste_type_name=wt,
                defaults={
                    "company_id": company,
                    "project_id": project,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            action = "Created" if created else "Exists"
            self.log(f"WasteType seeded: {wt} ({action})")

        self.log(f"---WasteTypes seeded ({len(self.WASTE_TYPES)} records)---")
