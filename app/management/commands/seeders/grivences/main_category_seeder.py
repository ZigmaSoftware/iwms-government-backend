from app.management.commands.seeders.base import BaseSeeder
from app.models.grivences.main_category_citizenGrievance import MainCategory


class MainCategorySeeder(BaseSeeder):
    name = "main_category"

    MAIN_CATEGORIES = [
        "Report issue",
        "Schedule pickup",
        "Pickup status",
        "Waste tips",
        "Collector info",
        "Billing inquiry",
        "Recycling info",
        "Complaint tracking",
        "Feedback",
        "Emergency pickup",
        "New service request",
        "Service cancellation",
        "Service modification",
        "Location update",
        "App support",
    ]

    def run(self):
        for category in self.MAIN_CATEGORIES:
            MainCategory.objects.get_or_create(
                main_categoryName=category,
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        self.log(f"---Main categories seeded ({len(self.MAIN_CATEGORIES)} records)---")
