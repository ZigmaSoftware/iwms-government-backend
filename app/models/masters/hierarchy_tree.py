"""
Closure-table hierarchy ("Hierarchy Tree").

A real-time, fully customisable geographical / organisational hierarchy that
does NOT require a separate Django project per client. Levels define the
template (Country, State, District, ...) and Nodes are the actual entries
(India, Tamil Nadu, Erode, ...). The closure table stores every
ancestor -> descendant relationship so reporting, breadcrumbs, roll-ups and
"everything under node X" queries are a single indexed lookup.

This is a NEW, self-contained feature. It is intentionally separate from the
flat ``AdministrativeHierarchy`` master so existing functionality is untouched.

Level skipping is supported: a node only needs a level whose ``order`` is
greater than its parent's level order. A "Street" can therefore live directly
under a "Country".
"""

from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_hierarchy_level_id():
    return f"HLVL-{generate_unique_id()}"


def generate_hierarchy_node_id():
    return f"HNODE-{generate_unique_id()}"


def generate_hierarchy_closure_id():
    return f"HCLS-{generate_unique_id()}"


class HierarchyLevel(BaseMaster):
    """
    A named tier in the hierarchy template, e.g. Country / State / Ward.

    ``order`` defines depth ranking. Children must sit at a strictly greater
    order than their parent, but the gap may be more than 1 (skip levels).
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_hierarchy_level_id,
        editable=False,
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100, blank=True, null=True)
    order = models.PositiveIntegerField()

    class Meta:
        db_table = "hierarchy_tree_level"
        ordering = ["order", "name"]
        unique_together = ("order",)

    def __str__(self):
        return f"{self.name} (order {self.order})"


class HierarchyNode(BaseMaster):
    """An actual entry in the hierarchy, e.g. India, Tamil Nadu, Erode."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_hierarchy_node_id,
        editable=False,
    )

    level = models.ForeignKey(
        HierarchyLevel,
        on_delete=models.PROTECT,
        related_name="nodes",
        to_field="unique_id",
        db_column="level_id",
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
        to_field="unique_id",
        db_column="parent_id",
    )

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=100, blank=True, null=True)
    custom_properties = models.JSONField(default=dict, blank=True)
    coordinates = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "hierarchy_tree_node"
        ordering = ["level__order", "name"]
        unique_together = ("parent", "name")
        indexes = [
            models.Index(fields=["parent"]),
            models.Index(fields=["level"]),
        ]

    def __str__(self):
        return self.name


class HierarchyClosure(BaseMaster):
    """
    One row per ancestor -> descendant pair (including self at depth 0).

    On node creation: copy every closure row whose descendant is the parent,
    increment depth by 1, then add a self row (depth 0).
    """

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_hierarchy_closure_id,
        editable=False,
    )

    ancestor = models.ForeignKey(
        HierarchyNode,
        on_delete=models.CASCADE,
        related_name="descendant_links",
        to_field="unique_id",
        db_column="ancestor_id",
    )

    descendant = models.ForeignKey(
        HierarchyNode,
        on_delete=models.CASCADE,
        related_name="ancestor_links",
        to_field="unique_id",
        db_column="descendant_id",
    )

    depth = models.PositiveIntegerField()

    class Meta:
        db_table = "hierarchy_tree_closure"
        unique_together = ("ancestor", "descendant")
        indexes = [
            models.Index(fields=["ancestor", "depth"]),
            models.Index(fields=["descendant", "depth"]),
        ]

    def __str__(self):
        return f"{self.ancestor_id} -> {self.descendant_id} (depth {self.depth})"
