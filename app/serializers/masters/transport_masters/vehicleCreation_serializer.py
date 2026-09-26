from rest_framework import serializers
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.masters.transport_masters.fuel import Fuel
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.validators.unique_name_validator import unique_name_validator
from app.utils import ref_cache


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
    # NOTE: state/district/area_type/corporation/.../panchayat/country are
    # plain CharFields (unique_id strings, no DB relation) — same convention
    # as WardSerializer. Input fields need no `source=` override since the
    # model's own field name already carries the "_id" suffix; display
    # names are resolved via SerializerMethodField, matching ward_serializer.py.

    # Read fields — return IDs and names in response

    # Write fields — accept IDs from frontend

    # Plain unique_id strings (no DB relation); checked in validate_*.
    vehicle_type_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    fuel_type_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    vehicle_type_name = serializers.SerializerMethodField()
    fuel_type_name = serializers.SerializerMethodField()

    def get_vehicle_type_name(self, obj):
        if not obj.vehicle_type_id:
            return None
        return getattr(ref_cache.get(VehicleTypeCreation, obj.vehicle_type_id), "vehicleType", None)

    def get_fuel_type_name(self, obj):
        if not obj.fuel_type_id:
            return None
        return getattr(ref_cache.get(Fuel, obj.fuel_type_id), "fuel_type", None)

    def validate_vehicle_type_id(self, value):
        if not value:
            return None
        if not VehicleTypeCreation.objects.filter(pk=value, is_deleted=False).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value

    def validate_fuel_type_id(self, value):
        if not value:
            return None
        if not Fuel.objects.filter(pk=value, is_deleted=False).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value

    # Government hierarchy — mirrors Collection Point's location fields
    # (see app/serializers/core_modules/schedule_setup/collection_point_serializer.py).
    country_id = serializers.CharField(required=False, allow_null=True)
    country_name = serializers.SerializerMethodField()
    state_id = serializers.CharField(required=False, allow_null=True)
    state_name = serializers.SerializerMethodField()
    district_id = serializers.CharField(required=False, allow_null=True)
    district_name = serializers.SerializerMethodField()
    area_type_id = serializers.CharField(required=False, allow_null=True)
    area_type_name = serializers.SerializerMethodField()
    corporation_id = serializers.CharField(required=False, allow_null=True)
    corporation_name = serializers.SerializerMethodField()
    municipality_id = serializers.CharField(required=False, allow_null=True)
    municipality_name = serializers.SerializerMethodField()
    town_panchayat_id = serializers.CharField(required=False, allow_null=True)
    town_panchayat_name = serializers.SerializerMethodField()
    panchayat_union_id = serializers.CharField(required=False, allow_null=True)
    panchayat_union_name = serializers.SerializerMethodField()
    panchayat_id = serializers.CharField(required=False, allow_null=True)
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

    class Meta:
        model = VehicleCreation
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
        instance = getattr(self, "instance", None)
        state_id = attrs.get("state_id") if "state_id" in attrs else getattr(instance, "state_id", None)
        country_id = attrs.get("country_id") if "country_id" in attrs else getattr(instance, "country_id", None)

        if state_id:
            state = State.objects.filter(unique_id=state_id).first()
            state_country_id = state.country_id if state else None
            if country_id and state_country_id and country_id != state_country_id:
                raise serializers.ValidationError(
                    {"country_id": "Country must match the selected state."}
                )
            attrs["country_id"] = state_country_id

        return unique_name_validator(
            Model=VehicleCreation,
            name_field="vehicle_no",
        )(self, attrs)
