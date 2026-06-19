from rest_framework import serializers
from app.models.masters.town_panchayat import TownPanchayat
from app.validators.unique_name_validator import unique_name_validator


class TownPanchayatSerializer(serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    area_type_name = serializers.CharField(source="area_type_id.name", read_only=True)

    class Meta:
        model = TownPanchayat
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "area_type_id",
            "area_type_name",
            "town_panchayat_name",
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
        town_panchayat_name = attrs.get("town_panchayat_name")

        if area_type and area_type.name != "Urban Local Body":
            raise serializers.ValidationError({
                "area_type_id": "Town Panchayat must belong to Urban Local Body."
            })

        if not self.instance or town_panchayat_name:
            unique_name_validator(
                Model=TownPanchayat,
                name_field="town_panchayat_name",
                scope_fields=["area_type_id", "district_id", "state_id"],
            )(self, attrs)

        return attrs
