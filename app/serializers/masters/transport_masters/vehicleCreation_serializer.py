from rest_framework import serializers
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.masters.transport_masters.fuel import Fuel
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.validators.unique_name_validator import unique_name_validator


class UniqueIdOrPkField(serializers.SlugRelatedField):
    def to_representation(self, value):
        return getattr(value, self.slug_field, None) or super().to_representation(value)

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except Exception:
            try:
                return self.get_queryset().get(pk=data)
            except Exception:
                raise


class VehicleCreationSerializer(serializers.ModelSerializer):

    # Read fields — return IDs and names in response

    # Write fields — accept IDs from frontend

    vehicle_type_id = UniqueIdOrPkField(
        source="vehicle_type",
        slug_field="unique_id",
        queryset=VehicleTypeCreation.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    fuel_type_id = UniqueIdOrPkField(
        source="fuel_type",
        slug_field="unique_id",
        queryset=Fuel.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )

    vehicle_type_name = serializers.CharField(
        source="vehicle_type.vehicleType",
        read_only=True
    )
    fuel_type_name = serializers.CharField(
        source="fuel_type.fuel_type",
        read_only=True
    )

    # Government hierarchy — mirrors Collection Point's location fields
    # (see app/serializers/schedule_masters/collection_point_serializer.py).
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

    class Meta:
        model = VehicleCreation
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
            "vehicle_type_id",
            "fuel_type_id",
            "vehicle_no",
            "capacity",
            "mileage_per_liter",
            "service_record",
            "vehicle_insurance",
            "insurance_expiry_date",
            "vehicle_condition",
            "fuel_tank_capacity",
            "rc_upload",
            "vehicle_insurance_file",
            "vehicle_type_name",
            "fuel_type_name",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):

        return unique_name_validator(
            Model=VehicleCreation,
            name_field="vehicle_no",
        )(self, attrs)
