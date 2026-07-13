from app.management.commands.seeders.base import BaseSeeder
from app.models.user_creations.waste_collection_bluetooth import WasteType


class WasteTypeSeeder(BaseSeeder):
    name = "WasteTypeSeeder"

    WASTE_TYPES = [
        # Primary segregated household streams — shown first in the operator app.
        "Wet Waste",
        "Dry Waste",
        "Organic Waste",
        "Plastic Waste",
        "Paper Waste",
        "Metal Waste",
        "Hazardous Waste",
    ]

    def run(self):
        for waste_type_name in self.WASTE_TYPES:
            obj, created = WasteType.objects.get_or_create(
                waste_type_name=waste_type_name,
                defaults={"is_deleted": False},
            )
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.save(update_fields=["is_deleted"])

        self.log(f"---Waste types seeded ({len(self.WASTE_TYPES)} records)---")
