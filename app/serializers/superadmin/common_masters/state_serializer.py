from rest_framework import serializers
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator

class StateSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    continent_id = serializers.SlugRelatedField(
        queryset=Continent.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    continent_name = serializers.CharField(source="continent_id.name", read_only=True)
    country_id = serializers.SlugRelatedField(
        queryset=Country.objects.filter(is_deleted=False),
        slug_field="unique_id",
        required=False,
        allow_null=True,
    )
    country_name = serializers.CharField(source="country_id.name", read_only=True)
    state_name = serializers.CharField(source="name", required=False)
    state_code = serializers.CharField(source="label", required=False, allow_blank=True, allow_null=True)
    name = serializers.CharField(required=False)
    label = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = State
        fields = [
            "unique_id",
            "state_name",
            "state_code",
            "name",
            "label",
            "coordinates",
            "continent_id",
            "continent_name",
            "country_id",
            "country_name",
            "is_active",
            "is_deleted",
            "created_by",
            "updated_by",
        ]
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        attrs.setdefault("continent_id", Continent.objects.filter(name__iexact="Asia", is_deleted=False).first())
        attrs.setdefault("country_id", Country.objects.filter(name__iexact="India", is_deleted=False).first())
        if not attrs.get("name"):
            raise serializers.ValidationError({"state_name": "This field is required."})
        if not attrs.get("continent_id"):
            raise serializers.ValidationError({"continent_id": "Default continent Asia was not found."})
        if not attrs.get("country_id"):
            raise serializers.ValidationError({"country_id": "Default country India was not found."})
        return unique_name_validator(
            Model=State,
            scope_fields=["continent_id", "country_id"]
        )(self, attrs)
