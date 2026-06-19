from rest_framework import serializers
from app.models.masters.panchayat import Panchayat
from app.validators.unique_name_validator import unique_name_validator


class PanchayatSerializer(serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    area_type_name = serializers.CharField(source="area_type_id.name", read_only=True)

    class Meta:
        model = Panchayat
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "area_type_id",
            "area_type_name",
            "panchayat_name",
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
        panchayat_name = attrs.get("panchayat_name")

        if area_type and area_type.name != "Rural Local Body":
            raise serializers.ValidationError({
                "area_type_id": "Panchayat must belong to Rural Local Body."
            })

        if not self.instance or panchayat_name:
            unique_name_validator(
                Model=Panchayat,
                name_field="panchayat_name",
                scope_fields=[
                    "area_type_id",
                    "district_id",
                    "state_id"
                ]
            )(self, attrs)

        return attrs
