from rest_framework import serializers
from app.models.common_masters.state import State
from app.validators.unique_name_validator import unique_name_validator

class StateSerializer( serializers.ModelSerializer):
    continent_name = serializers.CharField(source="continent_id.name", read_only=True)
    country_name = serializers.CharField(source="country_id.name", read_only=True)

    class Meta:
        model = State
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=State,
            scope_fields=["continent_id", "country_id"]
        )(self, attrs)
