from decimal import Decimal

from rest_framework import serializers


class ValidateBinQrRequestSerializer(serializers.Serializer):
    bin_qr = serializers.CharField(max_length=100, allow_blank=False)


class ScanBinRequestSerializer(serializers.Serializer):
    bin_qr = serializers.CharField(max_length=100, allow_blank=False)
    weight_kg = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
