from rest_framework import serializers
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.validators.unique_name_validator import unique_name_validator


class VehicleTypeCreationSerializer(serializers.ModelSerializer):

    company_name = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()
    company_id = serializers.SerializerMethodField()   # ← read as ID in response
    project_id = serializers.SerializerMethodField()   # ← read as ID in response

    # Write-only fields to accept IDs from frontend
    company_id_input = serializers.CharField(
        write_only=True, required=True, source="company_id"
    )
    project_id_input = serializers.CharField(
        write_only=True, required=False,
        allow_null=True, allow_blank=True,
        source="project_id"
    )

    class Meta:
        model = VehicleTypeCreation
        fields = [
            "unique_id",
            "vehicleType",
            "description",
            "is_active",
            "company_id",
            "company_id_input",
            "project_id",
            "project_id_input",
            "company_name",
            "project_name",
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
        attrs.pop("company_id", None)
        attrs.pop("project_id", None)

        return unique_name_validator(
            Model=VehicleTypeCreation,
            name_field="vehicleType",
        )(self, attrs)