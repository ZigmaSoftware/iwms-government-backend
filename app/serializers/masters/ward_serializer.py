from rest_framework import serializers

from app.models.masters.ward import Ward
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.serializers.superadmin.user_management.user_serializer import UniqueIdOrPkField
from app.utils.hierarchy import normalize_flat_geo_attrs


class WardSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    # ---- Geo hierarchy (write via *_id, read via nested objects) ----
    state_id = UniqueIdOrPkField(source="state", slug_field="unique_id", queryset=State.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    district_id = UniqueIdOrPkField(source="district", slug_field="unique_id", queryset=District.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    area_type_id = UniqueIdOrPkField(source="area_type", slug_field="unique_id", queryset=AreaType.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    corporation_id = UniqueIdOrPkField(source="corporation", slug_field="unique_id", queryset=Corporation.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    municipality_id = UniqueIdOrPkField(source="municipality", slug_field="unique_id", queryset=Municipality.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    town_panchayat_id = UniqueIdOrPkField(source="town_panchayat", slug_field="unique_id", queryset=TownPanchayat.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    panchayat_union_id = UniqueIdOrPkField(source="panchayat_union", slug_field="unique_id", queryset=PanchayatUnion.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)
    panchayat_id = UniqueIdOrPkField(source="panchayat", slug_field="unique_id", queryset=Panchayat.objects.filter(is_deleted=False), write_only=True, required=False, allow_null=True)

    state_name = serializers.CharField(source="state.name", read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    area_type_name = serializers.CharField(source="area_type.name", read_only=True)
    corporation_name = serializers.CharField(source="corporation.corporation_name", read_only=True)
    municipality_name = serializers.CharField(source="municipality.municipality_name", read_only=True)
    town_panchayat_name = serializers.CharField(source="town_panchayat.town_panchayat_name", read_only=True)
    panchayat_union_name = serializers.CharField(source="panchayat_union.union_name", read_only=True)
    panchayat_name = serializers.CharField(source="panchayat.panchayat_name", read_only=True)

    local_body_type = serializers.SerializerMethodField(read_only=True)
    local_body_name = serializers.SerializerMethodField(read_only=True)

    LOCAL_BODY_FIELDS = (
        ("corporation", "corporation_name"),
        ("municipality", "municipality_name"),
        ("town_panchayat", "town_panchayat_name"),
        ("panchayat_union", "union_name"),
        ("panchayat", "panchayat_name"),
    )

    def get_local_body_type(self, obj):
        for field, _ in self.LOCAL_BODY_FIELDS:
            if getattr(obj, field, None):
                return field
        return None

    def get_local_body_name(self, obj):
        for field, name_attr in self.LOCAL_BODY_FIELDS:
            value = getattr(obj, field, None)
            if value:
                return getattr(value, name_attr, None)
        return None

    class Meta:
        model = Ward
        fields = [
            "unique_id",
            "ward_name",
            "state_id", "state_name",
            "district_id", "district_name",
            "area_type_id", "area_type_name",
            "corporation_id", "corporation_name",
            "municipality_id", "municipality_name",
            "town_panchayat_id", "town_panchayat_name",
            "panchayat_union_id", "panchayat_union_name",
            "panchayat_id", "panchayat_name",
            "local_body_type",
            "local_body_name",
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
        errors = normalize_flat_geo_attrs(
            attrs,
            instance=getattr(self, "instance", None),
            require_geo=True,
        )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
