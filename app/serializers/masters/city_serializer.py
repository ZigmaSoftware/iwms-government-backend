from rest_framework import serializers
from app.models.masters.city import City
from app.validators.unique_name_validator import unique_name_validator

class CitySerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(source="continent_id.name", read_only=True)
    country_name   = serializers.CharField(source="country_id.name", read_only=True)
    state_name     = serializers.CharField(source="state_id.name", read_only=True)
    district_name  = serializers.CharField(source="district_id.name", read_only=True)
    

    class Meta:
        model = City
        fields = "__all__"
        read_only_fields = ["unique_id"]    
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=City,
            scope_fields=["continent_id", "country_id", "state_id", "district_id"]
        )(self, attrs)
