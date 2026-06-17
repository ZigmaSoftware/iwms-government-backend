from rest_framework import serializers
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.validators.unique_name_validator import unique_name_validator


class VehicleTypeCreationSerializer(serializers.ModelSerializer):


    # Write-only fields to accept IDs from frontend

    class Meta:
        model = VehicleTypeCreation
        fields = [
            "unique_id",
            "vehicleType",
            "description",
            "is_active",
        ]
        read_only_fields = ["unique_id"]
        validators = []

    def get_company_id(self, obj):
        company = getattr(obj, "company_id", None)
        return getattr(company, "unique_id", None)

    def get_project_id(self, obj):
        project = getattr(obj, "project_id", None)
        return getattr(project, "unique_id", None)

    def get_company_name(self, obj):
        company = getattr(obj, "company_id", None)
        return getattr(company, "name", None)

    def get_project_name(self, obj):
        project = getattr(obj, "project_id", None)
        return getattr(project, "name", None)

    def validate(self, attrs):

        return unique_name_validator(
            Model=VehicleTypeCreation,
            name_field="vehicleType",
        )(self, attrs)