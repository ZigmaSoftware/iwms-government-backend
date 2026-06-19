HIERARCHY_FIELDS = (
    "corporation_id",
    "municipality_id",
    "town_panchayat_id",
    "panchayat_union_id",
    "panchayat_id",
)

HIERARCHY_LABELS = {
    "corporation_id": "Corporation",
    "municipality_id": "Municipality",
    "town_panchayat_id": "Town Panchayat",
    "panchayat_union_id": "Panchayat Union",
    "panchayat_id": "Panchayat",
}


def selected_hierarchy_values(data_or_obj):
    values = {}
    for field in HIERARCHY_FIELDS:
        value = getattr(data_or_obj, field, None)
        if value:
            values[field] = value
    return values


def selected_hierarchy_from_attrs(attrs, instance=None):
    values = {}
    for field in HIERARCHY_FIELDS:
        if field in attrs:
            value = attrs.get(field)
        else:
            value = getattr(instance, field, None) if instance else None
        if value:
            values[field] = value
    return values


def copy_hierarchy(target, source, only_empty=False):
    for field in HIERARCHY_FIELDS:
        if only_empty and getattr(target, f"{field}_id", None):
            continue
        setattr(target, field, getattr(source, field, None))


def validate_single_hierarchy(attrs, instance=None, message="Select exactly one hierarchy level."):
    values = selected_hierarchy_from_attrs(attrs, instance)
    if len(values) != 1:
        from rest_framework import serializers

        raise serializers.ValidationError(message)


def filter_queryset_by_hierarchy(queryset, params):
    for field in HIERARCHY_FIELDS:
        value = params.get(field) or params.get(field.replace("_id", ""))
        if value:
            queryset = queryset.filter(**{f"{field}__unique_id": value})
    return queryset


def hierarchy_payload(obj):
    values = {}
    for field in HIERARCHY_FIELDS:
        related = getattr(obj, field, None)
        values[field] = getattr(related, "unique_id", None) if related else None
    return values
