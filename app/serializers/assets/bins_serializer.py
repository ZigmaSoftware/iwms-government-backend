from rest_framework import serializers
from app.models.assets.bins import Bins
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.services.hierarchy_tree_service import get_path
from app.validators.unique_name_validator import unique_name_validator

class BinsSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):

    location_node_name = serializers.CharField(source="location_node.name", read_only=True)
    location_level = serializers.CharField(source="location_node.level.name", read_only=True)
    location_path = serializers.SerializerMethodField(read_only=True)
    wastetype_name = serializers.CharField(source="wastetype_id.waste_type_name", read_only = True)
    collection_point_name = serializers.CharField(source="collection_point_id.cp_name", read_only = True)

    class Meta:
        model = Bins
        fields = [
            "unique_id",
            "location_node",
            "location_node_name",
            "location_level",
            "location_path",
            "collection_point_id",
            "collection_point_name",
            "bin_capacity",
            "bin_name",
            "bin_type",
            "bin_image",
            "bin_qr",
            "coordinates",
            "wastetype_id",
            "wastetype_name",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_active",
            "is_deleted"
        ]
        read_only_fields = [
            "unique_id",
            "location_node",
            "bin_qr",
            "created_at",
            "updated_at",
            "is_deleted"
        ]
        extra_kwargs = {
            "bin_qr": {"required": False, "read_only": True},
            "bin_image": {"required": False, "allow_blank": True},
        }


    def validate(self, attrs):
        if attrs.get("bin_qr") is None:
            attrs["bin_qr"] = ""

        if not attrs.get("bin_image"):
            attrs["bin_image"] = "default.png"
        
        if self.instance and "bin_name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=Bins,
            name_field="bin_name",
            scope_fields=["wastetype_id","collection_point_id"]
        )(self, attrs)

    def get_location_path(self, obj):
        if not obj.location_node_id:
            return []
        return [
            {"unique_id": e["unique_id"], "name": e["name"], "level_name": e.get("level_name")}
            for e in get_path(obj.location_node_id)
        ]
