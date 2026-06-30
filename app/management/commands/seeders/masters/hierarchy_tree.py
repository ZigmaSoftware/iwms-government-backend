"""
Seeds the closure-table Hierarchy Tree with an Erode example, including a
demonstration of the "skip hierarchy" feature (a Street created directly under
a Country).

Idempotent: clears the three hierarchy_tree_* tables then rebuilds, so running
it repeatedly always yields the same demo state without touching any other
master data.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.hierarchy_tree import (
    HierarchyClosure,
    HierarchyLevel,
    HierarchyNode,
)
from app.services import hierarchy_tree_service as svc


class HierarchyTreeSeeder(BaseSeeder):
    name = "HierarchyTreeSeeder"

    # Demo-only levels. Prefixed and placed in a high order band so they never
    # collide with the real geographic levels created by GeoToHierarchySeeder
    # (Continent..Panchayat = orders 1..6). This keeps the demo self-contained
    # and non-destructive to real geography.
    # (name, code, order)
    LEVELS = [
        ("Demo Country",      "DEMO_COUNTRY",      101),
        ("Demo State",        "DEMO_STATE",        102),
        ("Demo District",     "DEMO_DISTRICT",     103),
        ("Demo Municipality", "DEMO_MUNICIPALITY", 104),
        ("Demo Ward",         "DEMO_WARD",         105),
        ("Demo Street",       "DEMO_STREET",       106),
    ]

    # Straight chain (Demo) India -> ... -> Market Street (by level name).
    ERODE_CHAIN = [
        ("Demo Country",      "Demo India"),
        ("Demo State",        "Demo Tamil Nadu"),
        ("Demo District",     "Demo Erode"),
        ("Demo Municipality", "Demo Bhavani Municipality"),
        ("Demo Ward",         "Demo Ward 12"),
        ("Demo Street",       "Demo Market Street"),
    ]

    def run(self):
        # Non-destructive reset of ONLY this seeder's demo data (identified by
        # the demo level codes), so real geography is never touched.
        demo_codes = [code for _n, code, _o in self.LEVELS]
        demo_level_ids = list(
            HierarchyLevel.objects.filter(code__in=demo_codes).values_list("pk", flat=True)
        )
        demo_node_ids = list(
            HierarchyNode.objects.filter(level_id__in=demo_level_ids).values_list("pk", flat=True)
        )
        if demo_node_ids:
            HierarchyClosure.objects.filter(descendant_id__in=demo_node_ids).delete()
            # Strip leaves first (parent FK is PROTECT).
            remaining = set(demo_node_ids)
            while remaining:
                leaves = list(
                    HierarchyNode.objects.filter(pk__in=remaining, children__isnull=True)
                    .values_list("pk", flat=True)
                )
                if not leaves:
                    HierarchyNode.objects.filter(pk__in=remaining).delete()
                    break
                HierarchyNode.objects.filter(pk__in=leaves).delete()
                remaining -= set(leaves)
        HierarchyLevel.objects.filter(pk__in=demo_level_ids).delete()

        levels = {}
        for lname, code, order in self.LEVELS:
            level = HierarchyLevel.objects.create(name=lname, code=code, order=order)
            levels[lname] = level
        self.log(f"Demo levels seeded ({len(levels)} records).")

        # Build the straight demo Erode chain through the closure service.
        parent = None
        nodes_by_level = {}
        for level_name, node_name in self.ERODE_CHAIN:
            node = svc.create_node(
                level_id=levels[level_name].unique_id,
                parent_id=parent.unique_id if parent else None,
                name=node_name,
                code=node_name.upper().replace(" ", "-"),
            )
            nodes_by_level[level_name] = node
            parent = node
        self.log(f"Demo Erode chain seeded ({len(self.ERODE_CHAIN)} nodes).")

        # --- SKIP-LEVEL DEMO ---------------------------------------------
        # A Street created directly under the Country, skipping State / District
        # / Municipality / Ward. Only allowed because Street's level order is
        # greater than Country's.
        india = nodes_by_level["Demo Country"]
        skip_node = svc.create_node(
            level_id=levels["Demo Street"].unique_id,
            parent_id=india.unique_id,
            name="Demo Direct Street (skip demo)",
            code="DEMO-DIRECT-STREET",
        )
        self.log(
            f"Skip-level demo: '{skip_node.name}' (Demo Street) created directly "
            f"under '{india.name}' (Demo Country)."
        )

        self.log(
            f"Hierarchy Tree demo seeded: total now "
            f"{HierarchyNode.objects.count()} nodes, "
            f"{HierarchyClosure.objects.count()} closure rows."
        )
