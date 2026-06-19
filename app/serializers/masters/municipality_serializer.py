from rest_framework import serializers
from app.models.masters.municipality import Municipality
from app.validators.unique_name_validator import unique_name_validator


class MunicipalitySerializer(serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    area_type_name = serializers.CharField(source="area_type_id.name", read_only=True)
    hierarchy_name = serializers.CharField(source="hierarchy_id.level_name", read_only=True)
    hierarchy_order = serializers.IntegerField(source="hierarchy_id.hierarchy_order", read_only=True)

    class Meta:
        model = Municipality
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "area_type_id",
            "area_type_name",
            "hierarchy_id",
            "hierarchy_order",
            "hierarchy_name",
            "municipality_name",
            "description",
            "geofencing_type",
            "latitude",
            "longitude",
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
        municipality_name = attrs.get("municipality_name")

        if area_type and area_type.name.lower() != "urban":
            raise serializers.ValidationError({
                "area_type": "Municipality must belong to Urban area type."
            })

        if hierarchy and hierarchy.level_name.lower() != "municipality":
            raise serializers.ValidationError({
                "hierarchy": "Hierarchy level must be Municipality."
            })

        if not self.instance or municipality_name:
            unique_name_validator(
                Model=Municipality,
                name_field="municipality_name",
                scope_fields=["district_id", "state_id"],
            )(self, attrs)

        return attrs
