from decimal import Decimal

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.management.commands.seeders.ward_utils import geo_defaults_for_local_body, wards_for_district
from app.models.core_modules.schedule_setup.collection_point import Collection_point


class CollectionPointSeeder(BaseSeeder):
    """One collection point per Ward, across every local body type in the
    three operational districts (Erode/Coimbatore/Salem): Corporation,
    Municipality, Town Panchayat, Panchayat Union, and each Panchayat.
    Ward-scoped via Collection_point.wards, positioned at that ward's own
    seeded centroid, geo-scoped to the ward's parent local body."""

    name = "CollectionPointSeeder"

    def run(self):
        count = 0
        for district_name, geo in DISTRICTS.items():
            code = geo["code"]
            for idx, ward_info in enumerate(wards_for_district(district_name), start=1):
                ward = ward_info["ward"]
                point = (ward.coordinates or [None])[0]
                if not point:
                    self.log(f"Ward '{ward.ward_name}' has no coordinates — skipping its collection point.")
                    continue
                lat, lon = point["latitude"], point["longitude"]

                geo_defaults = geo_defaults_for_local_body(
                    ward_info["parent_type"], ward_info["parent"], include_country=True
                )
                cp, created = Collection_point.objects.update_or_create(
                    cp_name=f"CP-{code}-W{idx:03d}",
                    defaults={
                        **geo_defaults,
                        "latitude": Decimal(str(lat)),
                        "longitude": Decimal(str(lon)),
                        "coordinates": coordinates((lat, lon)),
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                cp.wards.set([ward])
                if created:
                    count += 1

        self.log(f"---Collection points seeded ({count} created)---")
