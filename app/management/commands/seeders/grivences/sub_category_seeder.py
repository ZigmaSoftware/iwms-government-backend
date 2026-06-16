from app.management.commands.seeders.base import BaseSeeder
from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.models.grivences.sub_category_citizenGrievance import SubCategory


class SubCategorySeeder(BaseSeeder):
    name = "sub_category"

    # Maps original 5 main categories → 3 sub-cats each = 15 total
    CATEGORY_MAP = {
        "Report issue": [
            "Missed Pickup",
            "Spillage / Overflow",
            "Broken Bin",
            "Staff Behavior",
            "Other",
        ],
        "Schedule pickup": [
            "Bulk Waste",
            "Garden Waste",
            "E-waste",
        ],
        "Pickup status": [
            "Track Pickup",
            "Track Complaint",
        ],
        "Waste tips": [
            "Recycling Tips",
            "Waste Segregation",
            "Composting Tips",
        ],
        "Collector info": [
            "Assigned Collector",
            "Collector Contact",
        ],
    }

    def run(self):
        total = 0
        for main_name, sub_list in self.CATEGORY_MAP.items():
            main_category = MainCategory.objects.filter(
                main_categoryName=main_name
            ).first()
            if not main_category:
                self.log(f"MainCategory '{main_name}' not found — skipping.")
                continue

            for sub_name in sub_list:
                SubCategory.objects.get_or_create(
                    name=sub_name,
                    mainCategory=main_category,
                    defaults={
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                total += 1

        self.log(f"---Sub categories seeded ({total} records)---")
