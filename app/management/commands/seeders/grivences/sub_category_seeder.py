from app.management.commands.seeders.base import BaseSeeder
from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.models.grivences.sub_category_citizenGrievance import SubCategory


class SubCategorySeeder(BaseSeeder):
    name = "sub_category"

    # One sub-category per main category — 5 total
    CATEGORY_MAP = {
        "Report issue":    "Missed Pickup",
        "Schedule pickup": "Bulk Waste",
        "Pickup status":   "Track Pickup",
        "Waste tips":      "Recycling Tips",
        "Billing inquiry": "Payment Query",
    }

    def run(self):
        total = 0
        for main_name, sub_name in self.CATEGORY_MAP.items():
            main_category = MainCategory.objects.filter(
                main_categoryName=main_name
            ).first()
            if not main_category:
                self.log(f"MainCategory '{main_name}' not found — skipping.")
                continue

            SubCategory.objects.get_or_create(
                name=sub_name,
                mainCategory=main_category,
                defaults={"is_active": True, "is_deleted": False},
            )
            total += 1

        self.log(f"---Sub categories seeded ({total} records)---")
