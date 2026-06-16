from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.masters.district import District
from app.validators.unique_name_validator import unique_name_validator

class DistrictSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):
    continent_name = serializers.CharField(source="continent_id.name", read_only=True)
    country_name   = serializers.CharField(source="country_id.name", read_only=True)
    state_name     = serializers.CharField(source="state_id.name", read_only=True)

    class Meta:
        model = District
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=District,
            scope_fields=["continent_id", "country_id", "state_id"]
        )(self, attrs)
