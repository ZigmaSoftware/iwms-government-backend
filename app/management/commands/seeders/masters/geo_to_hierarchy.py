"""
Mirror the existing static geographical masters into the closure-table
Hierarchy Tree so geography becomes dynamic without losing any data.

For every Continent / Country / State / District / AreaType / Panchayat row it
creates a matching HierarchyLevel (once) and HierarchyNode, preserving parent
links through the closure service. Each created node stores the originating geo
row's unique_id in ``custom_properties`` as ``{"source_type": ..., "source_id": ...}``
so dependents (customers, staff, users, panchayat leaders) can be backfilled to
point at the right node.

Idempotent and non-destructive: it never deletes or alters the old geo tables.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.hierarchy_tree import HierarchyLevel, HierarchyNode
from app.services import hierarchy_tree_service as svc


GEO_LEVELS = [
    ("Continent", "CONTINENT", 1),
    ("Country", "COUNTRY", 2),
    ("State", "STATE", 3),
    ("District", "DISTRICT", 4),
    ("Area Type", "AREA_TYPE", 5),
    # Urban / Rural local bodies sit under Area Type.
    ("Corporation", "CORPORATION", 6),
    ("Municipality", "MUNICIPALITY", 7),
    ("Town Panchayat", "TOWN_PANCHAYAT", 8),
    ("Panchayat Union", "PANCHAYAT_UNION", 9),
    ("Panchayat", "PANCHAYAT", 10),
]


class GeoToHierarchySeeder(BaseSeeder):
    name = "GeoToHierarchySeeder"

    def run(self):
        # Lazy imports so this is safe even while geo models are mid-migration.
        from app.models.common_masters.continent import Continent
        from app.models.common_masters.country import Country
        from app.models.common_masters.state import State
        from app.models.masters.district import District
        from app.models.masters.areatype import AreaType
        from app.models.masters.corporation import Corporation
        from app.models.masters.municipality import Municipality
        from app.models.masters.town_panchayat import TownPanchayat
        from app.models.masters.panchayat_union import PanchayatUnion
        from app.models.masters.panchayat import Panchayat

        levels = self._ensure_levels()

        # source_type+source_id -> created HierarchyNode, for parent wiring &
        # idempotency (re-running finds the existing node instead of duping).
        index = self._build_existing_index()

        def upsert(source_type, source_id, name, level_name, parent_node):
            key = (source_type, str(source_id))
            existing = index.get(key)
            if existing:
                return existing
            node = svc.create_node(
                level_id=levels[level_name].unique_id,
                parent_id=parent_node.unique_id if parent_node else None,
                name=name or str(source_id),
                code=str(source_id),
                custom_properties={"source_type": source_type, "source_id": str(source_id)},
            )
            index[key] = node
            return node

        created_before = HierarchyNode.objects.count()

        for cont in Continent.objects.filter(is_deleted=False):
            upsert("continent", cont.unique_id, cont.name, "Continent", None)

        for country in Country.objects.filter(is_deleted=False).select_related("continent_id"):
            parent = index.get(("continent", str(country.continent_id_id))) if country.continent_id_id else None
            upsert("country", country.unique_id, country.name, "Country", parent)

        for state in State.objects.filter(is_deleted=False):
            parent = index.get(("country", str(state.country_id_id))) if state.country_id_id else None
            upsert("state", state.unique_id, state.name, "State", parent)

        for district in District.objects.filter(is_deleted=False):
            parent = index.get(("state", str(district.state_id_id))) if district.state_id_id else None
            upsert("district", district.unique_id, district.name, "District", parent)

        for area in AreaType.objects.filter(is_deleted=False):
            parent = index.get(("district", str(area.district_id_id))) if area.district_id_id else None
            upsert("areatype", area.unique_id, area.name, "Area Type", parent)

        # Local bodies (under Area Type, falling back to District). Each carries
        # area_type_id / district_id FKs on its geo master.
        def _area_or_district(obj):
            return (
                index.get(("areatype", str(obj.area_type_id_id))) if getattr(obj, "area_type_id_id", None) else None
            ) or (
                index.get(("district", str(obj.district_id_id))) if getattr(obj, "district_id_id", None) else None
            )

        for corp in Corporation.objects.filter(is_deleted=False):
            upsert("corporation", corp.unique_id, corp.corporation_name, "Corporation", _area_or_district(corp))

        for muni in Municipality.objects.filter(is_deleted=False):
            upsert("municipality", muni.unique_id, muni.municipality_name, "Municipality", _area_or_district(muni))

        for tp in TownPanchayat.objects.filter(is_deleted=False):
            upsert("town_panchayat", tp.unique_id, tp.town_panchayat_name, "Town Panchayat", _area_or_district(tp))

        for pu in PanchayatUnion.objects.filter(is_deleted=False):
            upsert("panchayat_union", pu.unique_id, pu.union_name, "Panchayat Union", _area_or_district(pu))

        # Panchayats sit under their Area Type (falling back to District).
        for pan in Panchayat.objects.filter(is_deleted=False):
            parent = (
                index.get(("areatype", str(pan.area_type_id_id))) if pan.area_type_id_id else None
            ) or (
                index.get(("district", str(pan.district_id_id))) if pan.district_id_id else None
            )
            upsert("panchayat", pan.unique_id, pan.panchayat_name, "Panchayat", parent)

        created_after = HierarchyNode.objects.count()
        self.log(
            f"Geo mirrored into hierarchy: +{created_after - created_before} nodes "
            f"({created_after} total)."
        )

    def _ensure_levels(self):
        """
        Make the geo levels authoritative with a strictly-increasing order
        (Continent=1 ... Panchayat=6). Any non-geo level that collides on one of
        these orders is pushed above the geo band so the closure "child must be
        deeper than parent" rule always holds for geography.
        """
        geo_names = {name for name, _code, _order in GEO_LEVELS}
        geo_orders = {order for _name, _code, order in GEO_LEVELS}

        # Move conflicting non-geo levels (e.g. demo Country/State at low orders)
        # out of the geo order band [1..N].
        top = HierarchyLevel.objects.order_by("-order").first()
        next_free = (top.order if top else 0) + 1
        for lvl in HierarchyLevel.objects.filter(order__in=geo_orders).exclude(name__in=geo_names):
            lvl.order = next_free
            lvl.save(update_fields=["order"])
            next_free += 1

        levels = {}
        for name, code, order in GEO_LEVELS:
            level = HierarchyLevel.objects.filter(name=name).first()
            if level:
                if level.order != order:
                    level.order = order
                    level.save(update_fields=["order"])
            else:
                level = HierarchyLevel.objects.create(name=name, code=code, order=order)
            levels[name] = level
        return levels

    def _build_existing_index(self):
        index = {}
        for node in HierarchyNode.objects.filter(is_deleted=False):
            props = node.custom_properties or {}
            st, sid = props.get("source_type"), props.get("source_id")
            if st and sid:
                index[(st, str(sid))] = node
        return index
