from rest_framework import serializers

from app.models.masters.customer_masters.userchargerule import UserChargeRule
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.utils import ref_cache


class UserChargeRuleSerializer(
    
    serializers.ModelSerializer
):
    # Plain unique_id strings (no DB relation); checked in validate_*.
    property_id = serializers.CharField()
    subproperty_id = serializers.CharField()

    property_name = serializers.SerializerMethodField()
    subproperty_name = serializers.SerializerMethodField()

    def get_property_name(self, obj):
        return getattr(ref_cache.get(Property, obj.property_id, "unique_id"), "property_name", None)

    def get_subproperty_name(self, obj):
        return getattr(ref_cache.get(SubProperty, obj.subproperty_id, "unique_id"), "sub_property_name", None)

    def validate_property_id(self, value):
        if not Property.objects.filter(
            unique_id=value, is_active=True, is_deleted=False
        ).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value

    def validate_subproperty_id(self, value):
        if not SubProperty.objects.filter(
            unique_id=value, is_active=True, is_deleted=False
        ).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value

    amount = serializers.DecimalField(
        source="charge_amount",
        max_digits=10,
        decimal_places=2,
        required=False,
    )

    class Meta:
        model = UserChargeRule
        fields = [
            "unique_id",
            "property_id",
            "property_name",
            "subproperty_id",
            "subproperty_name",
            "is_bulk_waste_generator",
            "min_sqmtr_value",
            "max_sqmtr_value",
            "amount",
            "description",
            "is_deleted",
            "is_active",
        ]
        read_only_fields = ["unique_id"]
        validators = []

    def _resolved_value(self, attrs, field_name):
        if field_name in attrs:
            return attrs.get(field_name)

        instance = getattr(self, "instance", None)
        if instance is not None:
            return getattr(instance, field_name, None)

        return None

    def validate(self, attrs):
        is_bulk_waste_generator = self._resolved_value(
            attrs, "is_bulk_waste_generator"
        )
        min_sqmtr_value = self._resolved_value(attrs, "min_sqmtr_value")
        max_sqmtr_value = self._resolved_value(attrs, "max_sqmtr_value")
        amount = self._resolved_value(attrs, "charge_amount")
        property_uid = self._resolved_value(attrs, "property_id")
        subproperty_uid = self._resolved_value(attrs, "subproperty_id")
        property_obj = (
            Property.objects.filter(unique_id=property_uid).first() if property_uid else None
        )
        subproperty_obj = (
            SubProperty.objects.filter(unique_id=subproperty_uid).first()
            if subproperty_uid
            else None
        )

        if is_bulk_waste_generator is None:
            is_bulk_waste_generator = False

        errors = {}

        if property_obj is None:
            errors["property_id"] = "This field is required."

        if subproperty_obj is None:
            errors["subproperty_id"] = "This field is required."

        if (
            property_obj is not None
            and subproperty_obj is not None
            and subproperty_obj.property_id != property_obj.unique_id
        ):
            errors["subproperty_id"] = (
                "Selected subproperty does not belong to the selected property."
            )

        if amount is None:
            errors["amount"] = "Amount is required."

        if is_bulk_waste_generator:
            if min_sqmtr_value is not None:
                errors["min_sqmtr_value"] = (
                    "Must be null when is_bulk_waste_generator is true."
                )

            if max_sqmtr_value is not None:
                errors["max_sqmtr_value"] = (
                    "Must be null when is_bulk_waste_generator is true."
                )
        else:
            if min_sqmtr_value is None:
                errors["min_sqmtr_value"] = (
                    "This field is required when is_bulk_waste_generator is false."
                )

            if max_sqmtr_value is None:
                errors["max_sqmtr_value"] = (
                    "This field is required when is_bulk_waste_generator is false."
                )

            if (
                min_sqmtr_value is not None
                and max_sqmtr_value is not None
                and min_sqmtr_value >= max_sqmtr_value
            ):
                errors["non_field_errors"] = [
                    "min_sqmtr_value must be less than max_sqmtr_value."
                ]

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
