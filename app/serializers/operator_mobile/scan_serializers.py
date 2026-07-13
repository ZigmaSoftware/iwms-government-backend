from decimal import Decimal

from rest_framework import serializers


class ValidateBinQrRequestSerializer(serializers.Serializer):
    bin_qr = serializers.CharField(max_length=100, allow_blank=False)


class ScanBinRequestSerializer(serializers.Serializer):
    ACTION_COLLECT = "collect"
    ACTION_COLLECT_LATER = "collect_later"
    ACTION_NOT_AVAILABLE = "not_available"

    ACTION_CHOICES = [
        ACTION_COLLECT,
        ACTION_COLLECT_LATER,
        ACTION_NOT_AVAILABLE,
    ]

    bin_qr = serializers.CharField(max_length=100, allow_blank=False)
    action = serializers.ChoiceField(
        choices=ACTION_CHOICES,
        default=ACTION_COLLECT,
        required=False,
    )
    weight_kg = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        allow_null=True,
    )
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate(self, attrs):
        action = attrs.get("action") or self.ACTION_COLLECT
        weight = attrs.get("weight_kg")
        reason = (attrs.get("status_reason") or attrs.get("notes") or "").strip()

        if action == self.ACTION_COLLECT and weight is None:
            raise serializers.ValidationError({
                "weight_kg": "weight_kg is required when action is collect.",
            })
        if action != self.ACTION_COLLECT and not reason:
            raise serializers.ValidationError({
                "status_reason": "status_reason is required for this action.",
            })
        attrs["action"] = action
        attrs["status_reason"] = reason or None
        return attrs
