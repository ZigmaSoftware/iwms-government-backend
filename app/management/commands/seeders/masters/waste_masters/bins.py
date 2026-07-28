from decimal import Decimal

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.models.masters.waste_masters.bins import Bins, BinType
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.waste_masters.wastetype import WasteType

# Secondary bin collection points accept all 9 segregated waste streams —
# each ward's collection point gets a representative spread of 3 so every
# waste type appears across the district's wards.
WASTE_TYPE_CYCLE = [
    "Organic Waste",
    "Plastic Waste",
    "Paper Waste",
    "Metal Waste",
    "Hazardous Waste",
    "Wet Waste",
    "Dry Waste",
    "Mixed Waste",
    "Sanitary Waste",
]
BINS_PER_WARD = 3
BIN_TYPE_CYCLE = [BinType.SMALL, BinType.MEDIUM, BinType.LARGE]
CAPACITY_BY_TYPE = {BinType.SMALL: 120, BinType.MEDIUM: 240, BinType.LARGE: 660}


class BinSeeder(BaseSeeder):
    """3 bins per ward-level collection point, cycling through all 9 waste
    types so every ward offers a representative spread and every waste
    type is collected somewhere in each district. Ward FK set from the
    collection point's own ward (Bins.save() copies the rest of the flat
    geo block from collection_point_id automatically, but not ward)."""

    name = "BinSeeder"

    def run(self):
        cps = list(
            Collection_point.objects.filter(
                is_deleted=False,
                district__name__in=DISTRICTS.keys(),
                # Every ward-scoped collection point this seeder owns carries
                # exactly one Ward (see CollectionPointSeeder). Excludes
                # driver_user.py's own hand-picked demo collection points
                # (which never get a ward) — those already get their own
                # single dedicated bin directly from driver_user.py, and
                # should not also gain 3 generic segregated-waste bins once
                # they exist in a later seed run.
                wards__isnull=False,
            )
            .distinct()
            .prefetch_related("wards")
            .order_by("cp_name")
        )
        if not cps:
            self.log("No collection points found — run CollectionPointSeeder first.")
            return

        waste_types = {
            wt.waste_type_name: wt
            for wt in WasteType.objects.filter(
                waste_type_name__in=WASTE_TYPE_CYCLE, is_deleted=False
            )
        }
        if not waste_types:
            self.log("No WasteTypes found — run WasteTypeSeeder first.")
            return

        global_idx = 0
        count = 0
        for cp in cps:
            ward = cp.wards.first()

            for _slot in range(BINS_PER_WARD):
                waste_name = WASTE_TYPE_CYCLE[global_idx % len(WASTE_TYPE_CYCLE)]
                waste_type = waste_types.get(waste_name)
                bin_type = BIN_TYPE_CYCLE[global_idx % len(BIN_TYPE_CYCLE)]
                global_idx += 1
                if not waste_type:
                    continue

                bin_name = f"{waste_name.split(' ')[0]} Bin - {cp.cp_name}"
                _, created = Bins.objects.update_or_create(
                    collection_point_id=cp,
                    bin_name=bin_name,
                    wastetype_id=waste_type,
                    defaults={
                        "ward": ward,
                        "bin_capacity": CAPACITY_BY_TYPE[bin_type],
                        "bin_type": bin_type,
                        "bin_image": f"bin_images/{bin_name.replace(' ', '_').lower()}.png",
                        "latitude": Decimal(str(cp.latitude)),
                        "longitude": Decimal(str(cp.longitude)),
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if created:
                    count += 1

        self.log(f"---Bins seeded ({count} created)---")
