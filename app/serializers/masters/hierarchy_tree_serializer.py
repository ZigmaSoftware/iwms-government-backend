from rest_framework import serializers

from app.models.masters.hierarchy_tree import (
    HierarchyLevel,
    HierarchyNode,
)


class HierarchyLevelSerializer(serializers.ModelSerializer):

    class Meta:
        model = HierarchyLevel
        fields = [
            "unique_id",
            "name",
            "code",
            "order",
            "is_active",
        ]
        read_only_fields = ("unique_id",)


class HierarchyNodeSerializer(serializers.ModelSerializer):
    """
    Used for create/update/list/detail of nodes.

    ``level`` and ``parent`` are accepted/returned as their ``unique_id``
    values (SlugRelatedField) to match the rest of the codebase.
    """

    level = serializers.SlugRelatedField(
        queryset=HierarchyLevel.objects.filter(is_deleted=False),
        slug_field="unique_id",
    )
    level_name = serializers.CharField(source="level.name", read_only=True)
    level_order = serializers.IntegerField(source="level.order", read_only=True)

    parent = serializers.SlugRelatedField(
        queryset=HierarchyNode.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    parent_name = serializers.CharField(source="parent.name", read_only=True)

    class Meta:
        model = HierarchyNode
        fields = [
            "unique_id",
            "level",
            "level_name",
            "level_order",
            "parent",
            "parent_name",
            "name",
            "code",
            "custom_properties",
            "is_active",
        ]
        read_only_fields = ("unique_id",)
