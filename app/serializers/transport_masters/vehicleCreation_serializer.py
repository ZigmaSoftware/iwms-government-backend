from rest_framework import serializers
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.transport_masters.fuel import Fuel
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

    class Meta:
        model = VehicleCreation
        fields = [
            "unique_id",
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

    def get_company_id(self, obj):
        company = getattr(obj, "company_id", None)
        return getattr(company, "unique_id", None)

    def get_company_name(self, obj):
        company = getattr(obj, "company_id", None)
        return getattr(company, "name", None)

    def get_project_id(self, obj):
        project = getattr(obj, "project_id", None)
        return getattr(project, "unique_id", None)

    def get_project_name(self, obj):
        project = getattr(obj, "project_id", None)
        return getattr(project, "name", None)

    def validate(self, attrs):

        return unique_name_validator(
            Model=VehicleCreation,
            name_field="vehicle_no",
        )(self, attrs)