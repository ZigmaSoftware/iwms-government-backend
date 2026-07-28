from rest_framework import serializers
from app.models.masters.waste_masters.bins import Bins
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.validators.unique_name_validator import unique_name_validator
from app.serializers.superadmin.user_management.user_serializer import UniqueIdOrPkField
from app.utils.hierarchy import validate_wards_for_flat_geo

class BinsSerializer(serializers.ModelSerializer):

    country_id = UniqueIdOrPkField(source="country", slug_field="unique_id", queryset=Country.objects.filter(is_deleted=False), required=False, allow_null=True)
    country_name = serializers.CharField(source="country.name", read_only=True)
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
    ward_id = UniqueIdOrPkField(
        source="ward",
        slug_field="unique_id",
        queryset=Ward.objects.filter(is_deleted=False),
        required=True,
        allow_null=False,
    )
    ward_name = serializers.CharField(source="ward.ward_name", read_only=True)
    wastetype_name = serializers.CharField(source="wastetype_id.waste_type_name", read_only = True)
    collection_point_name = serializers.CharField(source="collection_point_id.cp_name", read_only = True)

    class Meta:
        model = Bins
        fields = [
            "unique_id",
            "country_id",
            "country_name",
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
            "ward_id",
            "ward_name",
            "collection_point_id",
            "collection_point_name",
            "bin_capacity",
            "bin_name",
            "bin_type",
            "bin_image",
            "bin_qr",
            "latitude",
            "longitude",
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
            "country_id",
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
        collection_point = attrs.get(
            "collection_point_id",
            getattr(self.instance, "collection_point_id", None),
        )
        ward = attrs.get("ward", getattr(self.instance, "ward", None))
        if not ward:
            if not self.instance or not self.partial:
                raise serializers.ValidationError({"ward_id": "Ward is required."})
        if not collection_point:
            raise serializers.ValidationError(
                {"collection_point_id": "Collection point is required."}
            )
        if ward and not collection_point.wards.filter(pk=ward.pk).exists():
            raise serializers.ValidationError(
                {"ward_id": "Ward must be one of the selected collection point's wards."}
            )
        if ward:
            ward_error = validate_wards_for_flat_geo(
                [ward],
                {
                    "corporation": collection_point.corporation,
                    "municipality": collection_point.municipality,
                    "town_panchayat": collection_point.town_panchayat,
                    "panchayat_union": collection_point.panchayat_union,
                    "panchayat": collection_point.panchayat,
                },
            )
            if ward_error:
                raise serializers.ValidationError({"ward_id": ward_error})

        latitude = attrs.get("latitude", getattr(self.instance, "latitude", None))
        longitude = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError(
                {"latitude": "Latitude and longitude must be provided together."}
            )
        if latitude is not None and not -90 <= latitude <= 90:
            raise serializers.ValidationError(
                {"latitude": "Latitude must be between -90 and 90."}
            )
        if longitude is not None and not -180 <= longitude <= 180:
            raise serializers.ValidationError(
                {"longitude": "Longitude must be between -180 and 180."}
            )

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
