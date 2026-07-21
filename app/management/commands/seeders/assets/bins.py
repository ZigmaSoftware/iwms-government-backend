from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.assets.bins import Bins, BinType
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.assets.wastetype import WasteType


class BinSeeder(BaseSeeder):
    name = "BinSeeder"

    # (collection_point_name, bin_name, waste_type_name, bin_capacity, bin_type, coordinates)
    BINS = [
        ("CP-Erode-Corp-01", "Organic Bin - Erode Corp", "Organic Waste", 120, BinType.SMALL, coordinates((11.3412, 77.7174), (11.3414, 77.7176))),
        ("CP-Bhavani-Muni-01", "Plastic Bin - Bhavani Muni", "Plastic Waste", 240, BinType.MEDIUM, coordinates((11.4439, 77.6847), (11.4441, 77.6849))),
        ("CP-Anthiyur-TP-01", "Paper Bin - Anthiyur TP", "Paper Waste", 120, BinType.SMALL, coordinates((11.5752, 77.5902), (11.5754, 77.5904))),
        ("CP-Anthiyur-PU-01", "Metal Bin - Anthiyur PU", "Metal Waste", 660, BinType.LARGE, coordinates((11.5662, 77.6042), (11.5664, 77.6044))),
        ("CP-Anthiyur-PLB-01", "Organic Bin - Anthiyur PLB", "Organic Waste", 120, BinType.SMALL, coordinates((11.3412, 77.5822), (11.3414, 77.5824))),
        ("CP-Bhavani-PLB-01", "Plastic Bin - Bhavani PLB", "Plastic Waste", 240, BinType.MEDIUM, coordinates((11.4439, 77.6847), (11.4441, 77.6849))),
        ("CP-Gobichettipalayam-PLB-01", "Paper Bin - Gobi PLB", "Paper Waste", 120, BinType.SMALL, coordinates((11.4526, 77.4357), (11.4528, 77.4359))),
        ("CP-Kavundampalayam-PLB-01", "Metal Bin - Kavundampalayam PLB", "Metal Waste", 660, BinType.LARGE, coordinates((11.2934, 77.6013), (11.2936, 77.6015))),
        ("CP-Modakkurichi-PLB-01", "Hazardous Bin - Modakkurichi PLB", "Hazardous Waste", 120, BinType.SMALL, coordinates((11.3807, 77.7034), (11.3809, 77.7036))),
    ]

    def run(self):
        if not Collection_point.objects.filter(is_deleted=False).exists():
            self.log("No collection points found — run CollectionPointSeeder first.")
            return

        count = 0
        for cp_name, bin_name, waste_name, capacity, bin_type, geo_coordinates in self.BINS:
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
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                count += 1

        self.log(f"---Bins seeded ({count} created)---")
