from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates, spread_points
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.management.commands.seeders.ward_utils import (
    WARDS_PER_LOCAL_BODY,
    ward_type_tag,
    local_bodies_for_district,
    local_body_ward_name,
)
from app.models.masters.corporation import Corporation
from app.models.masters.ward import Ward


class WardSeeder(BaseSeeder):
    """Seeds Wards under every local body type in the three operational
    districts (Erode/Coimbatore/Salem): Corporation, Municipality, Town
    Panchayat, Panchayat Union, and each named Panchayat. Corporation wards
    use real, curated locality names; every other local body gets
    deterministically generated "<Local Body> Ward N" wards spread around
    that local body's own seeded centroid (masters/{municipality,
    town_panchayat, panchayat_union, panchayat}.py already carry real
    coordinates — this reuses them rather than duplicating data)."""

    name = "WardSeeder"

    def run(self):
        count = 0
        for district_name in DISTRICTS:
            for lb in local_bodies_for_district(district_name):
                if lb["parent_type"] == "corporation":
                    count += self._seed_corporation_wards(district_name, lb["parent"])
                else:
                    count += self._seed_generated_wards(lb["parent_type"], lb["parent"])

        self.log(f"---Wards seeded ({count} created)---")

    def _seed_corporation_wards(self, district_name, corporation):
        geo = DISTRICTS[district_name]
        created_count = 0
        for ward_name, lat, lon in geo["corporation_wards"][:WARDS_PER_LOCAL_BODY["corporation"]]:
            _, created = Ward.objects.update_or_create(
                corporation=corporation,
                municipality=None,
                town_panchayat=None,
                panchayat_union=None,
                panchayat=None,
                ward_name=f"{ward_name}{ward_type_tag('corporation')}",
                defaults={
                    "state": corporation.state_id,
                    "district": corporation.district_id,
                    "area_type": corporation.area_type_id,
                    "coordinates": coordinates((lat, lon)),
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                created_count += 1
        return created_count

    def _seed_generated_wards(self, parent_type, parent):
        name_attr = {
            "municipality": "municipality_name",
            "town_panchayat": "town_panchayat_name",
            "panchayat_union": "union_name",
            "panchayat": "panchayat_name",
        }[parent_type]
        parent_name = getattr(parent, name_attr)
        count_needed = WARDS_PER_LOCAL_BODY[parent_type]

        centroid = (parent.coordinates or [None])[0]
        if not centroid:
            self.log(f"'{parent_name}' has no coordinates — skipping its wards.")
            return 0
        lat, lon = centroid["latitude"], centroid["longitude"]

        points = spread_points(lat, lon, count_needed, radius_km=1.5)
        created_count = 0
        base_filter = {
            "corporation": None, "municipality": None, "town_panchayat": None,
            "panchayat_union": None, "panchayat": None,
        }
        base_filter[parent_type] = parent

        for i, (w_lat, w_lon) in enumerate(points, start=1):
            _, created = Ward.objects.update_or_create(
                ward_name=local_body_ward_name(parent_name, i, parent_type),
                **base_filter,
                defaults={
                    "state": parent.state_id,
                    "district": parent.district_id,
                    "area_type": parent.area_type_id,
                    "coordinates": coordinates((w_lat, w_lon)),
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                created_count += 1
        return created_count
