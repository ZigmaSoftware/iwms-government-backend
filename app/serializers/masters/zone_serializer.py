# app/api/serializers/zone_serializer.py

from rest_framework import serializers
from app.models.masters.zone import Zone
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.validators.unique_name_validator import unique_name_validator


class ZoneSerializer(TenancyReadSerializerMixin,serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    country_id = serializers.CharField(source="state_id.country_id.unique_id", read_only=True)
    continent_id = serializers.CharField(source="state_id.continent_id.unique_id", read_only=True)
    country_name = serializers.CharField(source="state_id.country_id.name", read_only=True)
    continent_name = serializers.CharField(source="state_id.continent_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    hierarchy_name = serializers.CharField(source = "hierarchy_id.level_name", read_only = True)

    area_type_name = serializers.CharField(
        source="area_type_id.name",
        read_only=True
    )

    hierarchy_order = serializers.IntegerField(
        source="hierarchy_id.hierarchy_order",
        read_only=True
    )

    class Meta:
        model = Zone
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",

            "country_id",
            "country_name",
            "continent_id",
            "continent_name",

            "state_id",
            "state_name",
            "city_id",
            "city_name",
            "district_id",
            "district_name",

            "area_type_id",
            "area_type_name",

            "hierarchy_id",
            "hierarchy_order",
            "hierarchy_name",

            "zone_name",
            "description",

            "geofencing_type",
            
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
            "company_id",
            "project_id",
        ]

    def validate(self, attrs):

        # -------------------------------
        # GET VALUES (Handle Update Case)
        # -------------------------------
        area_type = attrs.get("area_type_id") or getattr(self.instance, "area_type_id", None)
        hierarchy = attrs.get("hierarchy_id") or getattr(self.instance, "hierarchy_id", None)
        zone_name = attrs.get("zone_name")

        # -------------------------------
        # 1️⃣ AreaType Must Be Urban
        # -------------------------------
        if area_type and area_type.name.lower() != "urban":
            raise serializers.ValidationError({
                "area_type": "zone must belong to urban area type."
            })

        # -------------------------------
        # 2️⃣ Hierarchy Must Be Panchayat
        # -------------------------------
        if hierarchy and hierarchy.level_name.lower() != "zone":
            raise serializers.ValidationError({
                "hierarchy": "Hierarchy level must be zone."
            })

        # -------------------------------
        # 3️⃣ Unique Panchayat Name
        # -------------------------------
        if not self.instance or zone_name:
            unique_name_validator(
                Model=Zone,
                name_field="zone_name",
                scope_fields=[
                    "company_id",
                    "project_id",
                    "city_id",
                    "district_id",
                    "state_id"
                ]
            )(self, attrs)

        return attrs