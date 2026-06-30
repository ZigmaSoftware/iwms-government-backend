"""
Generic hierarchy assignment.

Instead of every master carrying hard-coded geo columns (state_id, district_id,
country_id ...), ANY master row can be attached to ANY hierarchy node through a
single link table. The node already knows its full ancestry via the closure
table, so one assignment yields the entire chain for free (reporting, filtering,
permission scoping, breadcrumbs).

    HierarchyAssignment
    ───────────────────
      node         -> which HierarchyNode (e.g. the "Erode" node)
      entity_type  -> which master ("department", "customer", "staff", ...)
      entity_id    -> the unique_id (PK) of that master row
      is_primary   -> mark one assignment as the canonical location

This is the dynamic, config-driven replacement for the old static geographical
masters. Adding a new assignable master never requires a schema change here.
"""

from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.hierarchy_tree import HierarchyNode


def generate_hierarchy_assignment_id():
    return f"HASN-{generate_unique_id()}"


class HierarchyAssignment(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_hierarchy_assignment_id,
        editable=False,
    )

    node = models.ForeignKey(
        HierarchyNode,
        on_delete=models.CASCADE,
        related_name="assignments",
        to_field="unique_id",
        db_column="node_id",
    )

    # Logical master identity. entity_type is a free string key registered in
    # app/utils/hierarchy_entities.py; entity_id is that master's unique_id.
    entity_type = models.CharField(max_length=60)
    entity_id = models.CharField(max_length=60)

    # One assignment per entity may be flagged as its canonical/primary node.
    is_primary = models.BooleanField(default=True)

    # Optional human label cached at assignment time (handy for lists/audit).
    entity_label = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "hierarchy_assignment"
        ordering = ["entity_type", "entity_id"]
        unique_together = ("node", "entity_type", "entity_id")
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["node"]),
            models.Index(fields=["entity_type", "node"]),
        ]

    def __str__(self):
        return f"{self.entity_type}:{self.entity_id} -> {self.node_id}"
