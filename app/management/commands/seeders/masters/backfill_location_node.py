"""
Backfill ``location_node`` on dependents that still carry a legacy geo FK,
using the nodes created by GeoToHierarchySeeder, and create matching
HierarchyAssignment rows so the data is queryable through the generic API.

Customer and Staff are now node-only (they set location_node at creation), so
they no longer need backfilling. Only models still mid-migration are handled
here:
    PanchayatLeaderLogin.panchayat_id -> panchayat node

Idempotent and non-destructive. Runs after GeoToHierarchySeeder.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.hierarchy_tree import HierarchyNode
from app.services import hierarchy_assignment_service as svc


class BackfillLocationNodeSeeder(BaseSeeder):
    name = "BackfillLocationNodeSeeder"

    def run(self):
        from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin

        node_by_source = self._node_index()
        if not node_by_source:
            self.log("No mirrored geo nodes found — run GeoToHierarchySeeder first.")
            return

        counts = {"panchayat_leader": 0}

        # Panchayat leaders still have a legacy panchayat_id FK -> panchayat node.
        for leader in PanchayatLeaderLogin.objects.filter(is_deleted=False):
            node = node_by_source.get(("panchayat", str(leader.panchayat_id_id))) if leader.panchayat_id_id else None
            if node and self._link(leader, "unique_id", "panchayat_leader", node):
                counts["panchayat_leader"] += 1

        self.log(
            "Backfilled location_node: "
            + ", ".join(f"{k}={v}" for k, v in counts.items())
        )

    def _node_index(self):
        index = {}
        for node in HierarchyNode.objects.filter(is_deleted=False):
            props = node.custom_properties or {}
            st, sid = props.get("source_type"), props.get("source_id")
            if st and sid:
                index[(st, str(sid))] = node
        return index

    def _link(self, obj, pk_field, entity_type, node):
        """Set the direct FK and create a HierarchyAssignment. Returns True if changed."""
        changed = False
        if getattr(obj, "location_node_id", None) != node.unique_id:
            obj.location_node = node
            try:
                obj.save(update_fields=["location_node"])
                changed = True
            except Exception:
                pass
        try:
            svc.assign(
                node_id=node.unique_id,
                entity_type=entity_type,
                entity_id=str(getattr(obj, pk_field)),
                is_primary=True,
            )
        except Exception:
            pass
        return changed
