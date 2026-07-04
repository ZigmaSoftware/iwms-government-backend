from rest_framework import serializers

from app.models.schedule_masters.collection_point import Collection_point
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.services.hierarchy_tree_service import get_path
from app.validators.unique_name_validator import unique_name_validator
from app.utils.hierarchy import validate_single_hierarchy


class CollectionPointSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    location_node_name = serializers.CharField(source="location_node.name", read_only=True)
    location_level = serializers.CharField(source="location_node.level.name", read_only=True)
    location_path = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Collection_point
        fields = [
            "unique_id",
            "location_node",
            "location_node_name",
            "location_level",
            "location_path",
            "cp_name",
            "latitude",
            "longitude",
            "coordinates",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def get_location_path(self, obj):
        if not obj.location_node_id:
            return []
        return [
            {"unique_id": e["unique_id"], "name": e["name"], "level_name": e.get("level_name")}
            for e in get_path(obj.location_node_id)
        ]

    def validate(self, attrs):
        validate_single_hierarchy(
            attrs,
            self.instance,
            "Collection Point must belong to exactly one hierarchy level.",
        )

        if not self.instance or "cp_name" in attrs:
            unique_name_validator(
                Model=Collection_point,
                name_field="cp_name",
                scope_fields=["location_node"],
            )(self, attrs)

        return attrs
