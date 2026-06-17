from rest_framework import serializers

from app.models.customers.userchargerule import UserChargeRule
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class UserChargeRuleSerializer(
    
    serializers.ModelSerializer
):
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.filter(is_active=True, is_deleted=False)
    )
    subproperty_id = serializers.PrimaryKeyRelatedField(
        queryset=SubProperty.objects.filter(is_active=True, is_deleted=False)
    )

    property_name = serializers.CharField(
        source="property_id.property_name",
        read_only=True,
    )
    subproperty_name = serializers.CharField(
        source="subproperty_id.sub_property_name",
        read_only=True,
    )

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
        property_obj = self._resolved_value(attrs, "property_id")
        subproperty_obj = self._resolved_value(attrs, "subproperty_id")

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
            and subproperty_obj.property_id_id != property_obj.unique_id
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
