from rest_framework import serializers
from app.models.masters.waste_masters.property import Property
from app.validators.unique_name_validator import unique_name_validator

class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=Property,
            name_field="property_name",
        )(self, attrs)
