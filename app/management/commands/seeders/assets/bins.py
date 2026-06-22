from app.management.commands.seeders.base import BaseSeeder
from app.models.assets.bins import Bins, BinType
from app.models.schedule_masters.collection_point import Collection_point
from app.models.user_creations.waste_collection_bluetooth import WasteType


class BinSeeder(BaseSeeder):
    name = "BinSeeder"

    # (bin_name, bin_capacity, bin_type)
    BINS = [
        ("Organic Bin A",  120, BinType.SMALL),
        ("Plastic Bin A",  240, BinType.MEDIUM),
        ("Paper Bin A",    120, BinType.SMALL),
        ("Metal Bin A",    660, BinType.LARGE),
        ("Hazardous Bin A",120, BinType.SMALL),
    ]

    WASTE_TYPE_NAMES = [
        "Organic Waste",
        "Plastic Waste",
        "Paper Waste",
        "Metal Waste",
        "Hazardous Waste",
    ]

    def run(self):
        collection_points = list(
            Collection_point.objects.filter(is_deleted=False).order_by("cp_name")[:5]
        )
        if not collection_points:
            self.log("No collection points found — run CollectionPointSeeder first.")
            return

        count = 0
        for idx, (bin_name, capacity, bin_type) in enumerate(self.BINS):
            waste_name = self.WASTE_TYPE_NAMES[idx]
            waste_type = WasteType.objects.filter(
                waste_type_name=waste_name, is_deleted=False
            ).first()
            cp = collection_points[idx % len(collection_points)]

            if not waste_type:
                self.log(f"WasteType '{waste_name}' not found — skipping.")
                continue

            if Bins.objects.filter(bin_name=bin_name, collection_point_id=cp).exists():
                self.log(f"Bin '{bin_name}' at '{cp.cp_name}' already exists — skipping.")
                continue

            Bins.objects.create(
                collection_point_id=cp,
                wastetype_id=waste_type,
                bin_name=bin_name,
                bin_capacity=capacity,
                bin_type=bin_type,
                bin_image=f"bin_images/{bin_name.replace(' ', '_').lower()}.png",
                is_active=True,
                is_deleted=False,
            )
            count += 1

        self.log(f"---Bins seeded ({count} created)---")
