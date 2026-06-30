from app.models.masters.hierarchy_tree import HierarchyClosure, HierarchyNode


LOCATION_FIELD = "location_node"
LOCATION_QUERY_PARAMS = (
    "location_node",
    "location_node_id",
    "hierarchy_node",
    "hierarchy_node_id",
)

# Kept for older imports while the runtime model is now node-only.
HIERARCHY_FIELDS = (LOCATION_FIELD,)
HIERARCHY_LABELS = {LOCATION_FIELD: "Hierarchy Node"}


def _node_id(node_or_id):
    return getattr(node_or_id, "unique_id", node_or_id)


def selected_hierarchy_values(data_or_obj):
    node = getattr(data_or_obj, LOCATION_FIELD, None)
    return {LOCATION_FIELD: node} if node else {}


def selected_hierarchy_from_attrs(attrs, instance=None):
    if LOCATION_FIELD in attrs:
        node = attrs.get(LOCATION_FIELD)
    else:
        node = getattr(instance, LOCATION_FIELD, None) if instance else None
    return {LOCATION_FIELD: node} if node else {}


def copy_hierarchy(target, source, only_empty=False):
    if only_empty and getattr(target, "location_node_id", None):
        return
    setattr(target, LOCATION_FIELD, getattr(source, LOCATION_FIELD, None))


def validate_single_hierarchy(attrs, instance=None, message="Select a hierarchy node."):
    if not selected_hierarchy_from_attrs(attrs, instance):
        from rest_framework import serializers

        raise serializers.ValidationError(message)


def descendant_ids(node_or_id):
    node_id = _node_id(node_or_id)
    if not node_id:
        return []
    return list(
        HierarchyClosure.objects.filter(
            ancestor_id=node_id,
            is_deleted=False,
            descendant__is_deleted=False,
        ).values_list("descendant_id", flat=True)
    )


def node_contains(ancestor, descendant):
    ancestor_id = _node_id(ancestor)
    descendant_id = _node_id(descendant)
    if not ancestor_id or not descendant_id:
        return False
    return HierarchyClosure.objects.filter(
        ancestor_id=ancestor_id,
        descendant_id=descendant_id,
        is_deleted=False,
    ).exists()


def filter_queryset_by_hierarchy(queryset, params, field=LOCATION_FIELD):
    node_id = next((params.get(param) for param in LOCATION_QUERY_PARAMS if params.get(param)), None)
    if not node_id:
        return queryset
    ids = descendant_ids(node_id)
    if not ids:
        return queryset.none()
    return queryset.filter(**{f"{field}_id__in": ids})


def hierarchy_payload(obj):
    node = getattr(obj, LOCATION_FIELD, None)
    if not node:
        return {
            "location_node_id": None,
            "location_node_name": None,
            "location_level": None,
        }
    level = getattr(node, "level", None)
    return {
        "location_node_id": node.unique_id,
        "location_node_name": node.name,
        "location_level": getattr(level, "name", None),
    }


def legacy_geo_from_node(node):
    return {LOCATION_FIELD: node} if node else {}


def backfill_legacy_geo_from_node(attrs, *, node_attr=LOCATION_FIELD):
    return attrs


def agreed_weight_for_node(node):
    props = getattr(node, "custom_properties", None) or {}
    return props.get("agreed_weight_kg") or props.get("daily_agreed_weight_kg") or 0
