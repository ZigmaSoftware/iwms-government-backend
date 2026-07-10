from rest_framework import serializers
from app.models.schedule_masters.monthly_weight_report import MonthlyWeightReport
from app.utils.hierarchy import flat_geo_display


class MonthlyWeightReportSerializer(serializers.ModelSerializer):
    location_name = serializers.SerializerMethodField()
    location_level = serializers.SerializerMethodField()
    waste_type_name = serializers.CharField(
        source="waste_type_id.waste_type_name", read_only=True
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

    def get_location_name(self, obj):
        name, _level = flat_geo_display(obj)
        return name

    def get_location_level(self, obj):
        _name, level = flat_geo_display(obj)
        return level
