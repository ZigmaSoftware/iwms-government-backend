"""
Closure-table operations for the Hierarchy Tree feature.

Encapsulates node creation/update/move/delete and the read helpers
(tree, path, descendants, context) so the viewsets stay thin.

Closure maintenance on create:
    1. Insert the node with its parent_id.
    2. Copy every closure row whose descendant is the parent, depth + 1.
    3. Insert a self row (ancestor == descendant, depth 0).

Level skipping is allowed: a child's level order must merely be greater than
its parent's level order (not exactly +1). Root nodes (no parent) may use any
level.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from app.models.masters.hierarchy_tree import (
    HierarchyClosure,
    HierarchyLevel,
    HierarchyNode,
)


# ----------------------------------------------------------------------------
# Serialisation helpers
# ----------------------------------------------------------------------------

def node_to_dict(node, include_parent=True):
    data = {
        "unique_id": node.unique_id,
        "level_id": node.level_id,
        "level_name": node.level.name if node.level_id else None,
        "level_order": node.level.order if node.level_id else None,
        "parent_id": node.parent_id,
        "name": node.name,
        "code": node.code,
        "is_active": node.is_active,
        "custom_properties": node.custom_properties,
    }
    if include_parent and node.parent_id:
        data["parent_name"] = node.parent.name
    return data


# ----------------------------------------------------------------------------
# Write operations
# ----------------------------------------------------------------------------

def _active_nodes():
    return HierarchyNode.objects.filter(is_deleted=False)


@transaction.atomic
def create_node(*, level_id, parent_id=None, name, code="", custom_properties=None):
    level = HierarchyLevel.objects.get(unique_id=level_id, is_deleted=False)

    parent = None
    if parent_id:
        parent = (
            _active_nodes()
            .select_related("level")
            .get(unique_id=parent_id)
        )
        # Skip-level friendly: child order just has to be deeper than parent.
        if level.order <= parent.level.order:
            raise ValidationError(
                "Child level order must be greater than the parent level order."
            )

    node = HierarchyNode.objects.create(
        level=level,
        parent=parent,
        name=name,
        code=code or "",
        custom_properties=custom_properties or {},
    )

    if parent:
        ancestor_rows = HierarchyClosure.objects.filter(
            descendant=parent, is_deleted=False
        ).select_related("ancestor")
        HierarchyClosure.objects.bulk_create(
            [
                HierarchyClosure(
                    ancestor=row.ancestor,
                    descendant=node,
                    depth=row.depth + 1,
                )
                for row in ancestor_rows
            ]
        )

    HierarchyClosure.objects.create(ancestor=node, descendant=node, depth=0)
    return node


def _would_create_cycle(node, parent):
    if not parent:
        return False
    return HierarchyClosure.objects.filter(
        ancestor=node, descendant=parent, is_deleted=False
    ).exists()


@transaction.atomic
def _rebuild_subtree_closure(root):
    """Recompute closure rows for the subtree rooted at ``root`` after a move."""
    subtree_ids = list(
        HierarchyClosure.objects.filter(ancestor=root, is_deleted=False)
        .values_list("descendant_id", flat=True)
    )

    # Drop links that cross the subtree boundary (old ancestors -> subtree).
    HierarchyClosure.objects.filter(descendant_id__in=subtree_ids).exclude(
        ancestor_id__in=subtree_ids
    ).delete()

    subtree_nodes = HierarchyNode.objects.filter(
        unique_id__in=subtree_ids
    ).select_related("parent")

    for node in subtree_nodes:
        if not node.parent_id or node.parent_id in subtree_ids:
            continue
        parent_rows = HierarchyClosure.objects.filter(
            descendant=node.parent, is_deleted=False
        )
        descendant_rows = HierarchyClosure.objects.filter(
            ancestor=node, is_deleted=False
        )
        new_rows = []
        for parent_row in parent_rows:
            for descendant_row in descendant_rows:
                new_rows.append(
                    HierarchyClosure(
                        ancestor_id=parent_row.ancestor_id,
                        descendant_id=descendant_row.descendant_id,
                        depth=parent_row.depth + 1 + descendant_row.depth,
                    )
                )
        HierarchyClosure.objects.bulk_create(new_rows, ignore_conflicts=True)


@transaction.atomic
def update_node(node_id, *, level_id=None, parent_id=None, name=None, code=None,
                is_active=None, custom_properties=None):
    node = _active_nodes().select_related("level").get(unique_id=node_id)
    old_parent_id = node.parent_id
    old_level_id = node.level_id

    if level_id is not None:
        node.level = HierarchyLevel.objects.get(unique_id=level_id, is_deleted=False)

    if parent_id is not None:
        parent = None
        if parent_id:
            parent = (
                _active_nodes()
                .select_related("level")
                .get(unique_id=parent_id)
            )
            if parent.unique_id == node.unique_id or _would_create_cycle(node, parent):
                raise ValidationError(
                    "A node cannot be moved under itself or its descendants."
                )
            if node.level.order <= parent.level.order:
                raise ValidationError(
                    "Child level order must be greater than the parent level order."
                )
        node.parent = parent

    if name is not None:
        node.name = name
    if code is not None:
        node.code = code or ""
    if is_active is not None:
        node.is_active = is_active
    if custom_properties is not None:
        node.custom_properties = custom_properties

    node.save()

    if old_parent_id != node.parent_id or old_level_id != node.level_id:
        _rebuild_subtree_closure(node)
    return node


@transaction.atomic
def delete_subtree(node_id):
    """Soft-delete a node and every descendant, plus their closure rows."""
    node = _active_nodes().get(unique_id=node_id)
    subtree_ids = list(
        HierarchyClosure.objects.filter(ancestor=node, is_deleted=False)
        .values_list("descendant_id", flat=True)
    )

    HierarchyClosure.objects.filter(descendant_id__in=subtree_ids).delete()

    for descendant in (
        HierarchyNode.objects.filter(unique_id__in=subtree_ids, is_deleted=False)
        .select_related("level")
        .order_by("-level__order")
    ):
        descendant.delete()  # BaseMaster soft delete


# ----------------------------------------------------------------------------
# Read helpers
# ----------------------------------------------------------------------------

def get_descendants(node_id):
    node = _active_nodes().get(unique_id=node_id)
    links = (
        HierarchyClosure.objects.filter(ancestor=node, is_deleted=False)
        .select_related("descendant", "descendant__level", "descendant__parent")
        .order_by("depth", "descendant__level__order", "descendant__name")
    )
    return [
        {"depth": link.depth, **node_to_dict(link.descendant)}
        for link in links
        if not link.descendant.is_deleted
    ]


def get_path(node_id):
    node = _active_nodes().get(unique_id=node_id)
    links = (
        HierarchyClosure.objects.filter(descendant=node, is_deleted=False)
        .select_related("ancestor", "ancestor__level", "ancestor__parent")
        .order_by("-depth")
    )
    return [
        {"depth": link.depth, **node_to_dict(link.ancestor)}
        for link in links
        if not link.ancestor.is_deleted
    ]


def get_context(node_id):
    path = get_path(node_id)
    descendants = [item for item in get_descendants(node_id) if item["depth"] > 0]
    return path + descendants


def build_tree():
    nodes = list(
        _active_nodes()
        .select_related("level", "parent")
        .order_by("level__order", "name")
    )
    by_id = {n.unique_id: {**node_to_dict(n), "children": []} for n in nodes}
    roots = []
    for n in nodes:
        item = by_id[n.unique_id]
        if n.parent_id and n.parent_id in by_id:
            by_id[n.parent_id]["children"].append(item)
        else:
            roots.append(item)
    return roots
