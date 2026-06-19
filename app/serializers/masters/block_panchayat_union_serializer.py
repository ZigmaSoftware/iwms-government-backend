from rest_framework import serializers
from app.models.masters.block_panchayat_union import BlockPanchayatUnion
from app.validators.unique_name_validator import unique_name_validator


class BlockPanchayatUnionSerializer(serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only=True)
    district_name = serializers.CharField(source="district_id.name", read_only=True)
    area_type_name = serializers.CharField(source="area_type_id.name", read_only=True)
    hierarchy_name = serializers.CharField(source="hierarchy_id.level_name", read_only=True)
    hierarchy_order = serializers.IntegerField(source="hierarchy_id.hierarchy_order", read_only=True)

    class Meta:
        model = BlockPanchayatUnion
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
            "block_name",
            "description",
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
        block_name = attrs.get("block_name")

        if area_type and area_type.name.lower() != "rural":
            raise serializers.ValidationError({
                "area_type": "Block Panchayat Union must belong to Rural area type."
            })

        if hierarchy and hierarchy.level_name.lower() != "block panchayat union":
            raise serializers.ValidationError({
                "hierarchy": "Hierarchy level must be Block Panchayat Union."
            })

        if not self.instance or block_name:
            unique_name_validator(
                Model=BlockPanchayatUnion,
                name_field="block_name",
                scope_fields=["district_id", "state_id"],
            )(self, attrs)

        return attrs
