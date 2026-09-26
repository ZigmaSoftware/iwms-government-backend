from rest_framework import serializers

from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.superadmin.common_masters.state import State
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator
from app.utils import ref_cache


class CorporationSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    state_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    area_type_name = serializers.SerializerMethodField()

    def get_state_name(self, obj):
        return getattr(ref_cache.get(State, obj.state_id, "unique_id"), "name", None)

    def get_district_name(self, obj):
        return getattr(ref_cache.get(District, obj.district_id, "unique_id"), "name", None)

    def get_area_type_name(self, obj):
        return getattr(ref_cache.get(AreaType, obj.area_type_id, "unique_id"), "name", None)

    class Meta:
        model = Corporation
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "area_type_id",
            "area_type_name",
            "corporation_name",
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
        if area_type and area_type.name != "Urban Local Body":
            raise serializers.ValidationError({"area_type_id": "Corporation must belong to Urban Local Body."})

        return unique_name_validator(
            Model=Corporation,
            name_field="corporation_name",
            scope_fields=["state_id", "district_id", "area_type_id"],
        )(self, attrs)
