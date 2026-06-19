from rest_framework import serializers
from app.models.masters.ward import Ward
from app.serializers.masters.geofence import normalize_coordinates
from app.validators.unique_name_validator import unique_name_validator


class WardSerializer(serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    hierarchy_name = serializers.CharField(source="hierarchy_id.level_name", read_only=True)
    zone_name = serializers.CharField(source="zone_id.zone_name", read_only=True)

    continent_name = serializers.CharField(source="state_id.continent_id.name", read_only=True)
    country_name = serializers.CharField(source="state_id.country_id.name", read_only=True)
    continent_id = serializers.CharField(source="state_id.continent_id.unique_id", read_only=True)
    country_id = serializers.CharField(source="state_id.country_id.unique_id", read_only=True)

    area_type_name = serializers.CharField(
        source="area_type_id.name",
        read_only=True
    )

    hierarchy_order = serializers.IntegerField(
        source="hierarchy_id.hierarchy_order",
        read_only=True
    )

    class Meta:
        model = Ward
        fields = [
            "unique_id",

            "continent_id",
            "continent_name",
            "country_id",
            "country_name",

            "state_id",
            "state_name",
            "city_id",
            "city_name",
            "district_id",
            "district_name",

            "area_type_id",
            "area_type_name",
            "zone_id",
            "zone_name",

            "hierarchy_id",
            "hierarchy_order",
            "hierarchy_name",

            "ward_name",
            "description",

            "latitude",
            "longitude",
            "geofencing_type",
            "coordinates",

            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted",
        ]

        read_only_fields = [
            "unique_id",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):

        area_type = attrs.get("area_type_id") or getattr(self.instance, "area_type_id", None)
        hierarchy = attrs.get("hierarchy_id") or getattr(self.instance, "hierarchy_id", None)
        ward_name = attrs.get("ward_name")

        if area_type and area_type.name.lower() != "urban":
            raise serializers.ValidationError({
                "area_type": "ward must belong to urban area type."
            })

        if hierarchy and hierarchy.level_name.lower() != "ward":
            raise serializers.ValidationError({
                "hierarchy": "Hierarchy level must be ward."
            })

        if not self.instance or ward_name:
            unique_name_validator(
                Model=Ward,
                name_field="ward_name",
                scope_fields=[
                    "city_id",
                    "district_id",
                    "state_id"
                ]
            )(self, attrs)

        return attrs

    def validate_coordinates(self, value):
        return normalize_coordinates(value)
