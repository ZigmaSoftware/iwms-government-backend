# core/management/commands/seeders/base.py
from django.db import transaction


def node_for_source(source_type, source_obj):
    """Resolve the HierarchyNode mirrored from a legacy geo master.

    Geography is now a single `location_node` on dependent records. Seeders use
    this to translate the geo master they have (Panchayat, District, …) into the
    node to store. Returns None if no mirrored node exists yet.
    """
    if not source_obj:
        return None
    from app.models.masters.hierarchy_tree import HierarchyNode
    return HierarchyNode.objects.filter(
        is_deleted=False,
        custom_properties__source_type=source_type,
        custom_properties__source_id=source_obj.unique_id,
    ).first()


class BaseSeeder:
    name = "base"

    @transaction.atomic
    def run(self):
        raise NotImplementedError("---Seeder must implement run()---")

    def log(self, message):
        print(f"[{self.name.upper()}] {message}")

    def log_error(self, message):
        print(f"[{self.name.upper()} ERROR] {message}")