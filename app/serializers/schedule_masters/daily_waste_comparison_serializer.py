from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers
from app.models.schedule_masters.daily_waste_comparison import DailyWasteComparison

ZERO = Decimal("0")
TWO = Decimal("0.01")


def _rounded(value):
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


def _percent(numerator, denominator):
    d = Decimal(str(denominator))
    if d == ZERO:
        return ZERO
    return _rounded(Decimal(str(numerator)) / d * Decimal("100"))


def _status(actual, agreed):
    a, g = Decimal(str(actual)), Decimal(str(agreed))
    if a > g:
        return "Surplus"
    if a < g:
        return "Deficit"
    return "On Target"


class DailyWasteComparisonSerializer(serializers.ModelSerializer):
    panchayat_name = serializers.CharField(
        source="panchayat_id.panchayat_name", read_only=True
    )
    waste_type_name = serializers.CharField(
        source="waste_type_id.waste_type_name", read_only=True
    )

    class Meta:
        model = DailyWasteComparison
        fields = [
            "unique_id",
            "panchayat_id",
            "panchayat_name",
            "collection_date",
            "waste_type_id",
            "waste_type_name",
            "agreed_weight_kg",
            "actual_weight_kg",
            "variance_kg",
            "variance_percent",
            "report_status",
            "total_trips",
            "collection_points_covered",
        ]
        read_only_fields = [
            "unique_id",
            "variance_kg",
            "variance_percent",
            "report_status",
        ]

    def create(self, validated_data):
        agreed = validated_data.get("agreed_weight_kg", ZERO)
        actual = validated_data.get("actual_weight_kg", ZERO)
        validated_data["variance_kg"] = _rounded(Decimal(str(actual)) - Decimal(str(agreed)))
        validated_data["variance_percent"] = _percent(
            Decimal(str(actual)) - Decimal(str(agreed)), agreed
        )
        validated_data["report_status"] = _status(actual, agreed)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        agreed = validated_data.get("agreed_weight_kg", instance.agreed_weight_kg)
        actual = validated_data.get("actual_weight_kg", instance.actual_weight_kg)
        validated_data["variance_kg"] = _rounded(Decimal(str(actual)) - Decimal(str(agreed)))
        validated_data["variance_percent"] = _percent(
            Decimal(str(actual)) - Decimal(str(agreed)), agreed
        )
        validated_data["report_status"] = _status(actual, agreed)
        return super().update(instance, validated_data)
