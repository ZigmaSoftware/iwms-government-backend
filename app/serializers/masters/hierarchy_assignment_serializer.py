from rest_framework import serializers

from app.models.masters.hierarchy_assignment import HierarchyAssignment
from app.models.masters.hierarchy_tree import HierarchyNode


class HierarchyAssignmentSerializer(serializers.ModelSerializer):
    node = serializers.SlugRelatedField(
        queryset=HierarchyNode.objects.filter(is_deleted=False),
        slug_field="unique_id",
    )
    node_name = serializers.CharField(source="node.name", read_only=True)
    node_level = serializers.CharField(source="node.level.name", read_only=True)

    class Meta:
        model = HierarchyAssignment
        fields = [
            "unique_id",
            "node",
            "node_name",
            "node_level",
            "entity_type",
            "entity_id",
            "entity_label",
            "is_primary",
            "is_active",
        ]
        read_only_fields = ("unique_id", "entity_label")
