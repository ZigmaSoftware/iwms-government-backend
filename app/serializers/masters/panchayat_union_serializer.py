from rest_framework import serializers

from app.models.masters.panchayat_union import PanchayatUnion
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator


class PanchayatUnionSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    state_name = serializers.CharField(source="state_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    area_type_name = serializers.CharField(source="area_type_id.name", read_only=True)

    class Meta:
        model = PanchayatUnion
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "area_type_id",
            "area_type_name",
            "union_name",
            "coordinates",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def validate(self, attrs):
        area_type = attrs.get("area_type_id") or getattr(self.instance, "area_type_id", None)
        if area_type and area_type.name != "Rural Local Body":
            raise serializers.ValidationError({"area_type_id": "Panchayat Union must belong to Rural Local Body."})

        return unique_name_validator(
            Model=PanchayatUnion,
            name_field="union_name",
            scope_fields=["state_id", "district_id", "area_type_id"],
        )(self, attrs)
