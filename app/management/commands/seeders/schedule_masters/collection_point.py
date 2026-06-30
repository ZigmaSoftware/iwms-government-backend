from decimal import Decimal

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.schedule_masters.collection_point import Collection_point


# hierarchy_field (legacy) -> node custom_properties.source_type
_FIELD_TO_SOURCE = {
    "corporation_id": "corporation",
    "municipality_id": "municipality",
    "town_panchayat_id": "town_panchayat",
    "panchayat_union_id": "panchayat_union",
    "panchayat_id": "panchayat",
}


def _node_for(source_type, source_obj):
    if not source_obj:
        return None
    return HierarchyNode.objects.filter(
        is_deleted=False,
        custom_properties__source_type=source_type,
        custom_properties__source_id=source_obj.unique_id,
    ).first()


class CollectionPointSeeder(BaseSeeder):
    name = "CollectionPointSeeder"

    # (cp_name, hierarchy_field, hierarchy_name, latitude, longitude, coordinates)
    COLLECTION_POINTS = [
        ("CP-Erode-Corp-01", "corporation_id", "Erode Corporation", Decimal("11.3410"), Decimal("77.7172"), coordinates((11.3410, 77.7172), (11.3430, 77.7190))),
        ("CP-Bhavani-Muni-01", "municipality_id", "Bhavani Municipality", Decimal("11.4437"), Decimal("77.6845"), coordinates((11.4437, 77.6845), (11.4460, 77.6870))),
        ("CP-Anthiyur-TP-01", "town_panchayat_id", "Anthiyur Town Panchayat", Decimal("11.5750"), Decimal("77.5900"), coordinates((11.5750, 77.5900), (11.5770, 77.5920))),
        ("CP-Anthiyur-PU-01", "panchayat_union_id", "Anthiyur Panchayat Union", Decimal("11.5660"), Decimal("77.6040"), coordinates((11.5660, 77.6040), (11.5680, 77.6060))),
        ("CP-Anthiyur-PLB-01", "panchayat_id", "Anthiyur Panchayat", Decimal("11.3410"), Decimal("77.5820"), coordinates((11.3410, 77.5820), (11.3430, 77.5840))),
        ("CP-Bhavani-PLB-01", "panchayat_id", "Bhavani Panchayat", Decimal("11.4437"), Decimal("77.6845"), coordinates((11.4437, 77.6845), (11.4460, 77.6870))),
        ("CP-Gobichettipalayam-PLB-01", "panchayat_id", "Gobichettipalayam Panchayat", Decimal("11.4524"), Decimal("77.4355"), coordinates((11.4524, 77.4355), (11.4548, 77.4380))),
        ("CP-Kavundampalayam-PLB-01", "panchayat_id", "Kavundampalayam Panchayat", Decimal("11.2932"), Decimal("77.6011"), coordinates((11.2932, 77.6011), (11.2954, 77.6030))),
        ("CP-Modakkurichi-PLB-01", "panchayat_id", "Modakkurichi Panchayat", Decimal("11.3805"), Decimal("77.7032"), coordinates((11.3805, 77.7032), (11.3827, 77.7054))),
    ]
    LOOKUPS = {
        "corporation_id": (Corporation, "corporation_name"),
        "municipality_id": (Municipality, "municipality_name"),
        "town_panchayat_id": (TownPanchayat, "town_panchayat_name"),
        "panchayat_union_id": (PanchayatUnion, "union_name"),
        "panchayat_id": (Panchayat, "panchayat_name"),
    }

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        district = District.objects.filter(name="Erode", state_id=tamil_nadu).first()

        if not tamil_nadu or not district:
            self.log("Tamil Nadu / Erode not found — run StateSeeder and DistrictSeeder first.")
            return

        count = 0
        for cp_name, hierarchy_field, hierarchy_name, lat, lon, geo_coordinates in self.COLLECTION_POINTS:
            model, name_field = self.LOOKUPS[hierarchy_field]
            hierarchy_obj = model.objects.filter(
                **{name_field: hierarchy_name},
                is_deleted=False,
            ).select_related("district_id").first()
            if not hierarchy_obj:
                self.log(f"Hierarchy '{hierarchy_name}' not found — skipping.")
                continue

            # Geography is now a single hierarchy node.
            location_node = _node_for(_FIELD_TO_SOURCE[hierarchy_field], hierarchy_obj)
            if not location_node:
                self.log(f"No hierarchy node for '{hierarchy_name}' — run geo_to_hierarchy seeder first. Skipping.")
                continue

            _, created = Collection_point.objects.update_or_create(
                cp_name=cp_name,
                location_node=location_node,
                defaults={
                    "latitude": lat,
                    "longitude": lon,
                    "coordinates": geo_coordinates,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                count += 1

        self.log(f"---Collection points seeded ({count} created)---")
