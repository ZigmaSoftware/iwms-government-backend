"""
Backfill ``location_node`` on dependents from their old static geo FKs, using
the nodes created by GeoToHierarchySeeder, and create matching
HierarchyAssignment rows so the data is queryable through the generic API.

Maps:
    CustomerCreation.district/state/country  -> deepest available geo node
    StaffcreationOfficeDetails.district_id   -> district node
    User.district_id                         -> district node
    PanchayatLeaderLogin.panchayat_id        -> panchayat node

Idempotent and non-destructive. Runs after GeoToHierarchySeeder.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.hierarchy_tree import HierarchyNode
from app.services import hierarchy_assignment_service as svc


class BackfillLocationNodeSeeder(BaseSeeder):
    name = "BackfillLocationNodeSeeder"

    def run(self):
        from app.models.customers.customercreation import CustomerCreation
        from app.models.user_creations.staffcreation import StaffcreationOfficeDetails
        from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
        except Exception:
            User = None

        node_by_source = self._node_index()
        if not node_by_source:
            self.log("No mirrored geo nodes found — run GeoToHierarchySeeder first.")
            return

        counts = {"customer": 0, "staff": 0, "user": 0, "panchayat_leader": 0}

        # Customers: prefer district, then state, then country.
        for cust in CustomerCreation.objects.filter(is_deleted=False):
            node = (
                node_by_source.get(("district", str(cust.district_id))) if cust.district_id else None
            ) or (
                node_by_source.get(("state", str(cust.state_id))) if cust.state_id else None
            ) or (
                node_by_source.get(("country", str(cust.country_id))) if cust.country_id else None
            )
            if node and self._link(cust, "unique_id", "customer", node):
                counts["customer"] += 1

        # Staff -> district node.
        for staff in StaffcreationOfficeDetails.objects.filter(is_deleted=False):
            node = node_by_source.get(("district", str(staff.district_id_id))) if staff.district_id_id else None
            if node and self._link(staff, "staff_unique_id", "staff", node):
                counts["staff"] += 1

        # Panchayat leaders -> panchayat node.
        for leader in PanchayatLeaderLogin.objects.filter(is_deleted=False):
            node = node_by_source.get(("panchayat", str(leader.panchayat_id_id))) if leader.panchayat_id_id else None
            if node and self._link(leader, "unique_id", "panchayat_leader", node):
                counts["panchayat_leader"] += 1

        # Platform users -> district node (assignment optional; just set FK).
        if User is not None:
            for user in User.objects.all():
                did = getattr(user, "district_id_id", None)
                node = node_by_source.get(("district", str(did))) if did else None
                if node and getattr(user, "location_node_id", None) != node.unique_id:
                    user.location_node = node
                    try:
                        user.save(update_fields=["location_node"])
                        counts["user"] += 1
                    except Exception:
                        pass

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
