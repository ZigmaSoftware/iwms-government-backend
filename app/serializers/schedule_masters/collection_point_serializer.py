from rest_framework import serializers

from app.models.schedule_masters.collection_point import Collection_point
from app.models.common_masters.state import State
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


class CollectionPointSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    state_id = UniqueIdOrPkField(source="state", slug_field="unique_id", queryset=State.objects.filter(is_deleted=False), required=False, allow_null=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    district_id = UniqueIdOrPkField(source="district", slug_field="unique_id", queryset=District.objects.filter(is_deleted=False), required=True)
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

    class Meta:
        model = Collection_point
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

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        district = attrs.get("district") or getattr(instance, "district", None)
        if not district:
            raise serializers.ValidationError({"district_id": "Collection Point must be assigned to a district."})

        if not self.instance or "cp_name" in attrs:
            unique_name_validator(
                Model=Collection_point,
                name_field="cp_name",
                scope_fields=[
                    "district",
                    "corporation",
                    "municipality",
                    "town_panchayat",
                    "panchayat_union",
                    "panchayat",
                ],
            )(self, attrs)

        return attrs
