from rest_framework import serializers
from app.serializers.company_projects.tenancy import TenancyReadSerializerMixin
from app.models.masters.panchayat import Panchayat
from app.validators.unique_name_validator import unique_name_validator


class PanchayatSerializer(TenancyReadSerializerMixin, serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    city_name = serializers.CharField(source="city_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    area_type_name = serializers.CharField(source="area_type_id.name", read_only=True)
    hierarchy_order = serializers.IntegerField(source="hierarchy_id.hierarchy_order", read_only=True)
    hierarchy_name = serializers.CharField(source="hierarchy_id.level_name", read_only=True)
    block_name = serializers.CharField(source="block_id.block_name", read_only=True)

    class Meta:
        model = Panchayat
        fields = [
            "unique_id",
            "company_id",
            "company_name",
            "project_id",
            "project_name",
            "state_id",
            "state_name",
            "city_id",
            "city_name",
            "district_id",
            "district_name",
            "block_id",
            "block_name",
            "area_type_id",
            "area_type_name",
            "hierarchy_id",
            "hierarchy_order",
            "hierarchy_name",
            "panchayat_name",
            "agreed_weight_kg",
            "weight_unit",
            "effective_from",
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

        # -------------------------------
        # GET VALUES (Handle Update Case)
        # -------------------------------
        area_type = attrs.get("area_type_id") or getattr(self.instance, "area_type_id", None)
        hierarchy = attrs.get("hierarchy_id") or getattr(self.instance, "hierarchy_id", None)
        panchayat_name = attrs.get("panchayat_name")

        # -------------------------------
        # 1️⃣ AreaType Must Be Rural
        # -------------------------------
        if area_type and area_type.name.lower() != "rural":
            raise serializers.ValidationError({
                "area_type": "Panchayat must belong to Rural area type."
            })

        # -------------------------------
        # 2️⃣ Hierarchy Must Be Panchayat
        # -------------------------------
        if hierarchy and hierarchy.level_name.lower() != "panchayat":
            raise serializers.ValidationError({
                "hierarchy": "Hierarchy level must be Panchayat."
            })

        # -------------------------------
        # 3️⃣ Unique Panchayat Name
        # -------------------------------
        if not self.instance or panchayat_name:
            unique_name_validator(
                Model=Panchayat,
                name_field="panchayat_name",
                scope_fields=[
                    "company_id",
                    "project_id",
                    "city_id",
                    "district_id",
                    "state_id"
                ]
            )(self, attrs)

        return attrs
