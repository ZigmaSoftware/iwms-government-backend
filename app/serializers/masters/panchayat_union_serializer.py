from rest_framework import serializers

from app.models.masters.areatype import AreaType
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.district import District
from app.models.superadmin.common_masters.state import State
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator


class PanchayatUnionSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    state_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    area_type_name = serializers.SerializerMethodField()

    def get_state_name(self, obj):
        return State.objects.filter(unique_id=obj.state_id).values_list("name", flat=True).first()

    def get_district_name(self, obj):
        return District.objects.filter(unique_id=obj.district_id).values_list("name", flat=True).first()

    def get_area_type_name(self, obj):
        return AreaType.objects.filter(unique_id=obj.area_type_id).values_list("name", flat=True).first()

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
        area_type_id = attrs.get("area_type_id") or getattr(self.instance, "area_type_id", None)
        area_type = AreaType.objects.filter(unique_id=area_type_id).first() if area_type_id else None
        if area_type and area_type.name != "Rural Local Body":
            raise serializers.ValidationError({"area_type_id": "Panchayat Union must belong to Rural Local Body."})

        return unique_name_validator(
            Model=PanchayatUnion,
            name_field="union_name",
            scope_fields=["state_id", "district_id", "area_type_id"],
        )(self, attrs)
