from rest_framework import serializers
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator
from app.utils import ref_cache

class DistrictSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):
    continent_id = serializers.CharField(required=False, allow_null=True)
    continent_name = serializers.SerializerMethodField()
    country_id = serializers.CharField(required=False, allow_null=True)
    country_name = serializers.SerializerMethodField()
    state_name = serializers.SerializerMethodField()
    district_name = serializers.CharField(source="name", required=False)
    district_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    name = serializers.CharField(required=False)

    def get_continent_name(self, obj):
        return getattr(ref_cache.get(Continent, obj.continent_id, "unique_id"), "name", None)

    def get_country_name(self, obj):
        return getattr(ref_cache.get(Country, obj.country_id, "unique_id"), "name", None)

    def get_state_name(self, obj):
        return getattr(ref_cache.get(State, obj.state_id, "unique_id"), "name", None)

    class Meta:
        model = District
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_name",
            "district_code",
            "name",
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
        state_id = attrs.get("state_id") or getattr(self.instance, "state_id", None)
        if state_id:
            state = State.objects.filter(unique_id=state_id).first()
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
