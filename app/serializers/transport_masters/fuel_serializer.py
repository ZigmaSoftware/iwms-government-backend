from rest_framework import serializers
from app.models.transport_masters.fuel import Fuel
from app.validators.unique_name_validator import unique_name_validator

class FuelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fuel
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []  # disable DRF unique constraint

    def validate(self, attrs):
        return unique_name_validator(
            Model=Fuel,
            name_field="fuel_type",
        )(self, attrs)
