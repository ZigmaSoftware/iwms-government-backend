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
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.utils.hierarchy import validate_wards_for_flat_geo
from app.utils import ref_cache

class BinsSerializer(serializers.ModelSerializer):

    # state/district/area_type/corporation/.../panchayat/country are plain
    # CharFields (unique_id strings, no DB relation) copied automatically
    # from the parent Collection_point on save (see Bins.save()) — hence
    # read_only below, matching the pre-conversion behavior where these
    # fields could not be set directly either.
    country_id = serializers.CharField(read_only=True)
    country_name = serializers.SerializerMethodField()
    state_id = serializers.CharField(read_only=True)
    state_name = serializers.SerializerMethodField()
    district_id = serializers.CharField(read_only=True)
    district_name = serializers.SerializerMethodField()
    area_type_id = serializers.CharField(read_only=True)
    area_type_name = serializers.SerializerMethodField()
    corporation_id = serializers.CharField(read_only=True)
    corporation_name = serializers.SerializerMethodField()
    municipality_id = serializers.CharField(read_only=True)
    municipality_name = serializers.SerializerMethodField()
    town_panchayat_id = serializers.CharField(read_only=True)
    town_panchayat_name = serializers.SerializerMethodField()
    panchayat_union_id = serializers.CharField(read_only=True)
    panchayat_union_name = serializers.SerializerMethodField()
    panchayat_id = serializers.CharField(read_only=True)
    panchayat_name = serializers.SerializerMethodField()

    def get_country_name(self, obj):
        return getattr(ref_cache.get(Country, obj.country_id, "unique_id"), "name", None)

    def get_state_name(self, obj):
        return getattr(ref_cache.get(State, obj.state_id, "unique_id"), "name", None)

    def get_district_name(self, obj):
        return getattr(ref_cache.get(District, obj.district_id, "unique_id"), "name", None)

    def get_area_type_name(self, obj):
        return getattr(ref_cache.get(AreaType, obj.area_type_id, "unique_id"), "name", None)

    def get_corporation_name(self, obj):
        return getattr(ref_cache.get(Corporation, obj.corporation_id, "unique_id"), "corporation_name", None)

    def get_municipality_name(self, obj):
        return getattr(ref_cache.get(Municipality, obj.municipality_id, "unique_id"), "municipality_name", None)

    def get_town_panchayat_name(self, obj):
        return getattr(ref_cache.get(TownPanchayat, obj.town_panchayat_id, "unique_id"), "town_panchayat_name", None)

    def get_panchayat_union_name(self, obj):
        return getattr(ref_cache.get(PanchayatUnion, obj.panchayat_union_id, "unique_id"), "union_name", None)

    def get_panchayat_name(self, obj):
        return getattr(ref_cache.get(Panchayat, obj.panchayat_id, "unique_id"), "panchayat_name", None)

    # Ward / WasteType / Collection_point are plain unique_id strings (no DB
    # relation); existence is checked in the validate_* methods below.
    ward_id = serializers.CharField(required=True, allow_null=False)
    ward_name = serializers.SerializerMethodField()
    wastetype_id = serializers.CharField()
    wastetype_name = serializers.SerializerMethodField()
    collection_point_id = serializers.CharField()
    collection_point_name = serializers.SerializerMethodField()

    def get_ward_name(self, obj):
        return getattr(obj.ward, "ward_name", None)

    def get_wastetype_name(self, obj):
        return getattr(obj.wastetype, "waste_type_name", None)

    def get_collection_point_name(self, obj):
        return getattr(obj.collection_point, "cp_name", None)

    def validate_ward_id(self, value):
        if not Ward.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError(f'Invalid ward "{value}".')
        return value

    def validate_wastetype_id(self, value):
        if not WasteType.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value

    def validate_collection_point_id(self, value):
        if not Collection_point.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value

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
        collection_point_uid = attrs.get(
            "collection_point_id",
            getattr(self.instance, "collection_point_id", None),
        )
        collection_point = (
            Collection_point.objects.filter(unique_id=collection_point_uid).first()
            if collection_point_uid
            else None
        )
        ward_uid = attrs.get("ward_id", getattr(self.instance, "ward_id", None))
        ward = Ward.objects.filter(unique_id=ward_uid).first() if ward_uid else None
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
                    "corporation": collection_point.corporation_id,
                    "municipality": collection_point.municipality_id,
                    "town_panchayat": collection_point.town_panchayat_id,
                    "panchayat_union": collection_point.panchayat_union_id,
                    "panchayat": collection_point.panchayat_id,
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
