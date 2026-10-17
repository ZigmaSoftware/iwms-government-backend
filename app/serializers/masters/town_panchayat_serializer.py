from rest_framework import serializers
from app.models.masters.areatype import AreaType
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.district import District
from app.models.superadmin.common_masters.state import State
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator
from app.utils import ref_cache


class TownPanchayatSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):

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
        model = TownPanchayat
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "area_type_id",
            "area_type_name",
            "town_panchayat_name",
            "coordinates",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]
        read_only_fields = [
            "unique_id",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        area_type_id = attrs.get("area_type_id") or getattr(self.instance, "area_type_id", None)
        area_type = AreaType.objects.filter(unique_id=area_type_id).first() if area_type_id else None
        town_panchayat_name = attrs.get("town_panchayat_name")

        if area_type and area_type.name != "Urban Local Body":
            raise serializers.ValidationError({
                "area_type_id": "Town Panchayat must belong to Urban Local Body."
            })

        if not self.instance or town_panchayat_name:
            unique_name_validator(
                Model=TownPanchayat,
                name_field="town_panchayat_name",
                scope_fields=["area_type_id", "district_id", "state_id"],
            )(self, attrs)

        return attrs
