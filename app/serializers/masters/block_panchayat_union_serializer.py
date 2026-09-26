from rest_framework import serializers
from app.models.masters.block_panchayat_union import BlockPanchayatUnion
from app.models.masters.district import District
from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.validators.unique_name_validator import unique_name_validator
from app.utils import ref_cache


class BlockPanchayatUnionSerializer(serializers.ModelSerializer):

    state_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    area_type_id = serializers.CharField(required=False, allow_null=True)
    area_type_name = serializers.SerializerMethodField()
    hierarchy_id = serializers.CharField(required=False, allow_null=True)
    hierarchy_name = serializers.SerializerMethodField()
    hierarchy_order = serializers.SerializerMethodField()

    def get_area_type_name(self, obj):
        return getattr(obj.area_type, "name", None)

    def get_hierarchy_name(self, obj):
        return getattr(obj.hierarchy, "level_name", None)

    def get_hierarchy_order(self, obj):
        return getattr(obj.hierarchy, "hierarchy_order", None)

    def get_state_name(self, obj):
        return getattr(ref_cache.get(State, obj.state_id, "unique_id"), "name", None)

    def get_district_name(self, obj):
        return getattr(ref_cache.get(District, obj.district_id, "unique_id"), "name", None)

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
        area_type_uid = attrs.get("area_type_id") or getattr(self.instance, "area_type_id", None)
        hierarchy_uid = attrs.get("hierarchy_id") or getattr(self.instance, "hierarchy_id", None)
        area_type = AreaType.objects.filter(pk=area_type_uid).first() if area_type_uid else None
        hierarchy = (
            AdministrativeHierarchy.objects.filter(pk=hierarchy_uid).first()
            if hierarchy_uid
            else None
        )
        if area_type_uid and not area_type:
            raise serializers.ValidationError({"area_type_id": "Invalid area type."})
        if hierarchy_uid and not hierarchy:
            raise serializers.ValidationError({"hierarchy_id": "Invalid hierarchy."})
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
