from rest_framework import serializers
from app.models.masters.areatype import AreaType
from app.models.masters.district import District
from app.models.superadmin.common_masters.state import State
from app.serializers.masters.geofence import GeoCoordinateSerializerMixin
from app.validators.unique_name_validator import unique_name_validator


class AreaTypeSerializer(GeoCoordinateSerializerMixin, serializers.ModelSerializer):

    state_name = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    area_type_name = serializers.CharField(source="name", required=False)

    def get_state_name(self, obj):
        return State.objects.filter(unique_id=obj.state_id).values_list("name", flat=True).first()

    def get_district_name(self, obj):
        return District.objects.filter(unique_id=obj.district_id).values_list("name", flat=True).first()

    class Meta:
        model = AreaType
        fields = [
            "unique_id",
            "state_id",
            "state_name",
            "district_id",
            "district_name",
            "name",
            "area_type_name",
            "coordinates",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_deleted"
        ]
        read_only_fields = ("unique_id",)
        validators = []


    def validate(self, attrs):
        if self.instance and "name" not in attrs:
            return attrs

        return unique_name_validator(
            Model=AreaType,
            name_field="name",
            scope_fields=["district_id", "state_id"]
        )(self, attrs)
