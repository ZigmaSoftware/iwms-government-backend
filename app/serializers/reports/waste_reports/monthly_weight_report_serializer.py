from rest_framework import serializers
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.reports.waste_reports.monthly_weight_report import MonthlyWeightReport
from app.models.superadmin.common_masters.state import State
from app.utils.hierarchy import flat_geo_display

# state/district/area_type/... are plain unique_id CharFields, not
# ForeignKeys (see docs/geo_hierarchy_fk_removal.md), so the database no
# longer enforces that a stored id actually exists — checked here instead.
GEO_FIELD_MODELS = {
    "state": State,
    "district": District,
    "area_type": AreaType,
    "corporation": Corporation,
    "municipality": Municipality,
    "town_panchayat": TownPanchayat,
    "panchayat_union": PanchayatUnion,
    "panchayat": Panchayat,
}


class MonthlyWeightReportSerializer(serializers.ModelSerializer):
    location_name = serializers.SerializerMethodField()
    location_level = serializers.SerializerMethodField()
    waste_type_name = serializers.CharField(
        source="waste_type.waste_type_name", read_only=True, default=None
    )

    class Meta:
        model = MonthlyWeightReport
        fields = [
            "unique_id",
            "state",
            "district",
            "area_type",
            "corporation",
            "municipality",
            "town_panchayat",
            "panchayat_union",
            "panchayat",
            "location_name",
            "location_level",
            "month",
            "waste_type_id",
            "waste_type_name",
            "actual_weight_kg",
            "total_trips",
            "collection_points_covered",
        ]
        read_only_fields = ["unique_id"]

    def validate_waste_type_id(self, value):
        value = getattr(value, "unique_id", value)
        if not WasteType.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError("Invalid waste type.")
        return value

    def get_location_name(self, obj):
        name, _level = flat_geo_display(obj)
        return name

    def get_location_level(self, obj):
        _name, level = flat_geo_display(obj)
        return level

    def _validate_geo_id(self, field_name, value):
        if not value:
            return value
        model = GEO_FIELD_MODELS[field_name]
        if not model.objects.filter(unique_id=value).exists():
            raise serializers.ValidationError(
                f"No {model.__name__} found with unique_id '{value}'."
            )
        return value

    def validate_state(self, value):
        return self._validate_geo_id("state", value)

    def validate_district(self, value):
        return self._validate_geo_id("district", value)

    def validate_area_type(self, value):
        return self._validate_geo_id("area_type", value)

    def validate_corporation(self, value):
        return self._validate_geo_id("corporation", value)

    def validate_municipality(self, value):
        return self._validate_geo_id("municipality", value)

    def validate_town_panchayat(self, value):
        return self._validate_geo_id("town_panchayat", value)

    def validate_panchayat_union(self, value):
        return self._validate_geo_id("panchayat_union", value)

    def validate_panchayat(self, value):
        return self._validate_geo_id("panchayat", value)
