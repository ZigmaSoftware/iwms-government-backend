# app/api/serializers/hierarchy_serializer.py

from rest_framework import serializers
from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy


class AdministrativeHierarchySerializer(serializers.ModelSerializer):

    # area_type is a plain unique_id string (no ForeignKey/DB relation) —
    # see docs/geo_hierarchy_fk_removal.md — so its display name is looked
    # up explicitly instead of traversed via a dotted `source`.
    area_type_name = serializers.SerializerMethodField(read_only=True)

    class Meta:

        model = AdministrativeHierarchy
        fields = [
            "unique_id",
            "level_name",
            "area_type",
            "area_type_name",
            "is_active",
        ]
        read_only_fields = ("unique_id",)

    def get_area_type_name(self, obj):
        return (
            AreaType.objects.filter(unique_id=obj.area_type)
            .values_list("name", flat=True)
            .first()
        )