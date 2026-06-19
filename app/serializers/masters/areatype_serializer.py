# app/api/serializers/area_type_serializer.py

from rest_framework import serializers
from app.models.masters.areatype import AreaType
from app.validators.unique_name_validator import unique_name_validator


class AreaTypeSerializer(serializers.ModelSerializer):

    state_name = serializers.CharField(source="state_id.name", read_only = True)
    city_name = serializers.CharField(source="city_id.name", read_only = True)
    district_name = serializers.CharField(source="district_id.name", read_only = True)

    class Meta:
        model = AreaType
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "city_id",
            "city_name",
            "district_id",
            "district_name",
            "name",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted"
        ]
        read_only_fields = ("unique_id",)


        def validate(self, attrs):
        
            if self.instance and "name" not in attrs:
                return attrs

            return unique_name_validator(
                Model=AreaType,
                name_field="name", 
                scope_fields=["city_id","district_id","state_id"]  
            )(self, attrs)