from rest_framework import serializers
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.masters.district import District
from app.validators.unique_name_validator import unique_name_validator

class DistrictSerializer(serializers.ModelSerializer):
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
    country_name   = serializers.CharField(source="country_id.name", read_only=True)
    state_name     = serializers.CharField(source="state_id.name", read_only=True)
    district_name = serializers.CharField(source="name", required=False)
    district_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    name = serializers.CharField(required=False)

    class Meta:
        model = District
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_name",
            "district_code",
            "name",
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
        state = attrs.get("state_id") or getattr(self.instance, "state_id", None)
        if state:
            attrs.setdefault("continent_id", state.continent_id)
            attrs.setdefault("country_id", state.country_id)
        if not attrs.get("name"):
            raise serializers.ValidationError({"district_name": "This field is required."})
        if not attrs.get("state_id"):
            raise serializers.ValidationError({"state_id": "This field is required."})
        if not attrs.get("continent_id"):
            raise serializers.ValidationError({"continent_id": "This field is required."})
        if not attrs.get("country_id"):
            raise serializers.ValidationError({"country_id": "This field is required."})

        return unique_name_validator(
            Model=District,
            scope_fields=["continent_id", "country_id", "state_id"]
        )(self, attrs)
