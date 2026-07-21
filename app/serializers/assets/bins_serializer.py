from rest_framework import serializers
from app.models.assets.bins import Bins
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator
from app.serializers.user_creations.user_serializer import UniqueIdOrPkField

class BinsSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):

    state_id = UniqueIdOrPkField(source="state", slug_field="unique_id", queryset=State.objects.filter(is_deleted=False), required=False, allow_null=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    district_id = UniqueIdOrPkField(source="district", slug_field="unique_id", queryset=District.objects.filter(is_deleted=False), required=False, allow_null=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    area_type_id = UniqueIdOrPkField(source="area_type", slug_field="unique_id", queryset=AreaType.objects.filter(is_deleted=False), required=False, allow_null=True)
    area_type_name = serializers.CharField(source="area_type.name", read_only=True)
    corporation_id = UniqueIdOrPkField(source="corporation", slug_field="unique_id", queryset=Corporation.objects.filter(is_deleted=False), required=False, allow_null=True)
    corporation_name = serializers.CharField(source="corporation.corporation_name", read_only=True)
    municipality_id = UniqueIdOrPkField(source="municipality", slug_field="unique_id", queryset=Municipality.objects.filter(is_deleted=False), required=False, allow_null=True)
    municipality_name = serializers.CharField(source="municipality.municipality_name", read_only=True)
    town_panchayat_id = UniqueIdOrPkField(source="town_panchayat", slug_field="unique_id", queryset=TownPanchayat.objects.filter(is_deleted=False), required=False, allow_null=True)
    town_panchayat_name = serializers.CharField(source="town_panchayat.town_panchayat_name", read_only=True)
    panchayat_union_id = UniqueIdOrPkField(source="panchayat_union", slug_field="unique_id", queryset=PanchayatUnion.objects.filter(is_deleted=False), required=False, allow_null=True)
    panchayat_union_name = serializers.CharField(source="panchayat_union.union_name", read_only=True)
    panchayat_id = UniqueIdOrPkField(source="panchayat", slug_field="unique_id", queryset=Panchayat.objects.filter(is_deleted=False), required=False, allow_null=True)
    panchayat_name = serializers.CharField(source="panchayat.panchayat_name", read_only=True)
    wastetype_name = serializers.CharField(source="wastetype_id.waste_type_name", read_only = True)
    collection_point_name = serializers.CharField(source="collection_point_id.cp_name", read_only = True)

    class Meta:
        model = Bins
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "area_type_id",
            "area_type_name",
            "corporation_id",
            "corporation_name",
            "municipality_id",
            "municipality_name",
            "town_panchayat_id",
            "town_panchayat_name",
            "panchayat_union_id",
            "panchayat_union_name",
            "panchayat_id",
            "panchayat_name",
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
            "state_id",
            "district_id",
            "area_type_id",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
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
