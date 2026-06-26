"""
Service for the generic HierarchyAssignment link table.

Read paths use the closure table so a query for a node returns entities
assigned to that node AND everything beneath it (roll-up), which is the whole
point of the closure design.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from app.models.masters.hierarchy_tree import HierarchyClosure, HierarchyNode
from app.models.masters.hierarchy_assignment import HierarchyAssignment
from app.utils.hierarchy_entities import entity_label, get_entity_config


def assignment_to_dict(assignment, *, include_path=False):
    node = assignment.node
    data = {
        "unique_id": assignment.unique_id,
        "node": assignment.node_id,
        "node_name": node.name if node else None,
        "node_level": node.level.name if node and node.level_id else None,
        "entity_type": assignment.entity_type,
        "entity_id": assignment.entity_id,
        "entity_label": assignment.entity_label,
        "is_primary": assignment.is_primary,
        "is_active": assignment.is_active,
    }
    if include_path:
        data["path"] = _node_path(assignment.node_id)
    return data


def _node_path(node_id):
    """Ancestry chain root -> ... -> node, from the closure table."""
    links = (
        HierarchyClosure.objects.filter(descendant_id=node_id, is_deleted=False)
        .select_related("ancestor", "ancestor__level")
        .order_by("-depth")
    )
    return [
        {
            "unique_id": link.ancestor_id,
            "name": link.ancestor.name,
            "level_name": link.ancestor.level.name if link.ancestor.level_id else None,
            "depth": link.depth,
        }
        for link in links
        if not link.ancestor.is_deleted
    ]


@transaction.atomic
def assign(*, node_id, entity_type, entity_id, is_primary=True):
    if not get_entity_config(entity_type):
        raise ValidationError(f"Unknown entity_type '{entity_type}'.")

    node = HierarchyNode.objects.filter(unique_id=node_id, is_deleted=False).first()
    if not node:
        raise ValidationError("Hierarchy node not found.")

    label = entity_label(entity_type, entity_id)
    if label is None:
        raise ValidationError(
            f"No '{entity_type}' record found for id '{entity_id}'."
        )

    # If this assignment is primary, demote any other primary for the entity.
    if is_primary:
        HierarchyAssignment.objects.filter(
            entity_type=entity_type, entity_id=entity_id, is_primary=True, is_deleted=False
        ).update(is_primary=False)

    assignment, _created = HierarchyAssignment.objects.update_or_create(
        node=node,
        entity_type=entity_type,
        entity_id=entity_id,
        defaults={
            "is_primary": is_primary,
            "entity_label": label,
            "is_active": True,
            "is_deleted": False,
        },
    )
    return assignment


@transaction.atomic
def unassign(assignment_id):
    assignment = HierarchyAssignment.objects.filter(
        unique_id=assignment_id, is_deleted=False
    ).first()
    if not assignment:
        raise ValidationError("Assignment not found.")
    assignment.delete()  # BaseMaster soft delete


def for_entity(entity_type, entity_id):
    """All node assignments for one master record (with ancestry paths)."""
    qs = (
        HierarchyAssignment.objects.filter(
            entity_type=entity_type, entity_id=entity_id, is_deleted=False
        )
        .select_related("node", "node__level")
        .order_by("-is_primary")
    )
    return [assignment_to_dict(a, include_path=True) for a in qs]


def under_node(node_id, *, entity_type=None, include_descendants=True):
    """
    Entities assigned to a node. With ``include_descendants`` (default) it
    rolls up through the closure table: a Customer on "Erode" also appears when
    you query the "Tamil Nadu" or "India" node above it.
    """
    if include_descendants:
        node_ids = list(
            HierarchyClosure.objects.filter(ancestor_id=node_id, is_deleted=False)
            .values_list("descendant_id", flat=True)
        )
    else:
        node_ids = [node_id]

    qs = (
        HierarchyAssignment.objects.filter(node_id__in=node_ids, is_deleted=False)
        .select_related("node", "node__level")
        .order_by("entity_type", "entity_id")
    )
    if entity_type:
        qs = qs.filter(entity_type=entity_type)
    return [assignment_to_dict(a) for a in qs]
