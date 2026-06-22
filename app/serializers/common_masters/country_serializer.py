from rest_framework import serializers
from app.models.common_masters.country import Country
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator

class CountrySerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    continent_name = serializers.CharField(
        source="continent_id.name", read_only=True
    )

    class Meta:
        model = Country
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=Country,
            scope_fields=["continent_id"]
        )(self, attrs)
