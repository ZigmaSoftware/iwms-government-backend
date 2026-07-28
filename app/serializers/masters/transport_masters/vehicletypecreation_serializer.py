from rest_framework import serializers
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
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

    def validate(self, attrs):

        return unique_name_validator(
            Model=VehicleTypeCreation,
            name_field="vehicleType",
        )(self, attrs)
