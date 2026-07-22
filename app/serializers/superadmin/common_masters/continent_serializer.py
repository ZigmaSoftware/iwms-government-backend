from rest_framework import serializers
from app.models.superadmin.common_masters.continent import Continent
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator

class ContinentSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Continent
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []  # disable DRF unique constraint

    def validate(self, attrs):
        return unique_name_validator(       
            Model=Continent,
            name_field="name",
        )(self, attrs)
