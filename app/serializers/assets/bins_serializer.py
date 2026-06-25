from rest_framework import serializers
from app.models.assets.bins import Bins
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator

class BinsSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):

    panchayat_name = serializers.CharField(source="collection_point_id.panchayat_id.panchayat_name", read_only = True)
    panchayat_id = serializers.CharField(source="collection_point_id.panchayat_id.unique_id", read_only = True)
    corporation_id = serializers.CharField(source="collection_point_id.corporation_id.unique_id", read_only=True)
    corporation_name = serializers.CharField(source="collection_point_id.corporation_id.corporation_name", read_only=True)
    municipality_id = serializers.CharField(source="collection_point_id.municipality_id.unique_id", read_only=True)
    municipality_name = serializers.CharField(source="collection_point_id.municipality_id.municipality_name", read_only=True)
    town_panchayat_id = serializers.CharField(source="collection_point_id.town_panchayat_id.unique_id", read_only=True)
    town_panchayat_name = serializers.CharField(source="collection_point_id.town_panchayat_id.town_panchayat_name", read_only=True)
    panchayat_union_id = serializers.CharField(source="collection_point_id.panchayat_union_id.unique_id", read_only=True)
    panchayat_union_name = serializers.CharField(source="collection_point_id.panchayat_union_id.union_name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    wastetype_name = serializers.CharField(source="wastetype_id.waste_type_name", read_only = True)
    collection_point_name = serializers.CharField(source="collection_point_id.cp_name", read_only = True)

    class Meta:
        model = Bins
        fields = [
            "unique_id",
            "panchayat_id",
            "panchayat_name",
            "corporation_id",
            "corporation_name",
            "municipality_id",
            "municipality_name",
            "town_panchayat_id",
            "town_panchayat_name",
            "panchayat_union_id",
            "panchayat_union_name",
            "district_id",
            "district_name",
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
