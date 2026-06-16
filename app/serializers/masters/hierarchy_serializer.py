# app/api/serializers/hierarchy_serializer.py

from rest_framework import serializers
from app.models.masters.hierarchy import AdministrativeHierarchy


class AdministrativeHierarchySerializer(serializers.ModelSerializer):

    area_type_name = serializers.CharField(source = "area_type.name", read_only = True)

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