from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.waste_masters.bins import Bins, BinType
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.waste_masters.wastetype import WasteType


class BinSeeder(BaseSeeder):
    name = "BinSeeder"

    # (collection_point_name, bin_name, waste_type_name, bin_capacity, bin_type, latitude, longitude)
    BINS = [
        ("CP-Erode-Corp-01", "Organic Bin - Erode Corp", "Organic Waste", 120, BinType.SMALL, 11.3412, 77.7174),
        ("CP-Bhavani-Muni-01", "Plastic Bin - Bhavani Muni", "Plastic Waste", 240, BinType.MEDIUM, 11.4439, 77.6847),
        ("CP-Anthiyur-TP-01", "Paper Bin - Anthiyur TP", "Paper Waste", 120, BinType.SMALL, 11.5752, 77.5902),
        ("CP-Anthiyur-PU-01", "Metal Bin - Anthiyur PU", "Metal Waste", 660, BinType.LARGE, 11.5662, 77.6042),
        ("CP-Anthiyur-PLB-01", "Organic Bin - Anthiyur PLB", "Organic Waste", 120, BinType.SMALL, 11.3412, 77.5822),
        ("CP-Bhavani-PLB-01", "Plastic Bin - Bhavani PLB", "Plastic Waste", 240, BinType.MEDIUM, 11.4439, 77.6847),
        ("CP-Gobichettipalayam-PLB-01", "Paper Bin - Gobi PLB", "Paper Waste", 120, BinType.SMALL, 11.4526, 77.4357),
        ("CP-Kavundampalayam-PLB-01", "Metal Bin - Kavundampalayam PLB", "Metal Waste", 660, BinType.LARGE, 11.2934, 77.6013),
        ("CP-Modakkurichi-PLB-01", "Hazardous Bin - Modakkurichi PLB", "Hazardous Waste", 120, BinType.SMALL, 11.3807, 77.7034),
    ]

    def run(self):
        if not Collection_point.objects.filter(is_deleted=False).exists():
            self.log("No collection points found — run CollectionPointSeeder first.")
            return

        count = 0
        for cp_name, bin_name, waste_name, capacity, bin_type, latitude, longitude in self.BINS:
            waste_type = WasteType.objects.filter(
                waste_type_name=waste_name, is_deleted=False
            ).first()
            cp = Collection_point.objects.filter(cp_name=cp_name, is_deleted=False).first()

            if not waste_type:
                self.log(f"WasteType '{waste_name}' not found — skipping.")
                continue
            if not cp:
                self.log(f"Collection point '{cp_name}' not found — skipping.")
                continue

            _, created = Bins.objects.update_or_create(
                collection_point_id=cp,
                bin_name=bin_name,
                wastetype_id=waste_type,
                defaults={
                    "bin_capacity": capacity,
                    "bin_type": bin_type,
                    "bin_image": f"bin_images/{bin_name.replace(' ', '_').lower()}.png",
                    "latitude": latitude,
                    "longitude": longitude,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                count += 1

        self.log(f"---Bins seeded ({count} created)---")
