from django.db import transaction
from rest_framework import serializers

from app.models.masters.customer_masters.customer_access_configuration import (
    CustomerAccessConfiguration,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.utils.app_feature_grants import CITIZEN_APP_SCREENS


class CustomerAccessConfigurationSerializer(serializers.ModelSerializer):
    """Per-customer app access.

    Customers have no web screens — every citizen route is middleware-exempt
    and hard-scoped to the signed-in customer — so this is the one place where
    app screens are ticked directly rather than inherited from the shared
    permission list. Those ticks gate the app's UI; the module ticks gate
    whether they can sign in at all.
    """

    customer_unique_id = serializers.CharField(write_only=True, required=False)
    app_module_ids = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    app_screen_ids = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    customer_name = serializers.CharField(source="customer_id.customer_name", read_only=True)
    contact_no = serializers.CharField(source="customer_id.contact_no", read_only=True)

    class Meta:
        model = CustomerAccessConfiguration
        exclude = ("app_modules", "app_screens")
        read_only_fields = ["unique_id", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["customer_id"] = instance.customer_id_id

        modules = instance.app_modules.filter(is_deleted=False)
        data["app_module_ids"] = [m.unique_id for m in modules]
        data["app_module_keys"] = [m.surface_key for m in modules]

        screens = instance.app_screens.filter(is_deleted=False)
        data["app_screen_ids"] = [s.unique_id for s in screens]
        data["app_screen_names"] = [s.userscreen_name for s in screens]
        return data

    def validate(self, attrs):
        customer_id = self.initial_data.get("customer_unique_id") or self.initial_data.get(
            "customer_id"
        )
        if customer_id:
            customer = CustomerCreation.objects.filter(
                unique_id=customer_id, is_deleted=False
            ).first()
            if not customer:
                raise serializers.ValidationError(
                    {"customer_unique_id": f"No customer '{customer_id}'."}
                )
            attrs["resolved_customer"] = customer
        elif not self.instance:
            raise serializers.ValidationError(
                {"customer_unique_id": "This field is required."}
            )

        screen_ids = self.initial_data.get("app_screen_ids")
        if screen_ids:
            allowed = set(
                UserScreen.objects.filter(
                    userscreen_name__in=CITIZEN_APP_SCREENS, is_deleted=False
                ).values_list("unique_id", flat=True)
            )
            unknown = set(screen_ids) - allowed
            if unknown:
                raise serializers.ValidationError(
                    {
                        "app_screen_ids": (
                            "Only citizen app screens can be granted to a customer. "
                            f"Not citizen screens: {sorted(unknown)}"
                        )
                    }
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        customer = validated_data.pop("resolved_customer")
        validated_data.pop("customer_unique_id", None)
        module_ids = validated_data.pop("app_module_ids", [])
        screen_ids = validated_data.pop("app_screen_ids", [])

        instance, _ = CustomerAccessConfiguration.objects.update_or_create(
            customer_id=customer,
            defaults={
                "description": validated_data.get("description", ""),
                "is_active": True,
                "is_deleted": False,
            },
        )
        self._apply(instance, module_ids, screen_ids)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        customer = validated_data.pop("resolved_customer", None)
        validated_data.pop("customer_unique_id", None)
        module_ids = validated_data.pop("app_module_ids", None)
        screen_ids = validated_data.pop("app_screen_ids", None)

        if customer:
            instance.customer_id = customer
        instance.description = validated_data.get("description", instance.description)
        instance.save()

        self._apply(
            instance,
            module_ids if "app_module_ids" in self.initial_data else None,
            screen_ids if "app_screen_ids" in self.initial_data else None,
        )
        return instance

    @staticmethod
    def _apply(instance, module_ids, screen_ids):
        """Omitted lists leave existing ticks alone, so a partial update
        cannot silently revoke a customer's app access."""
        if module_ids is not None:
            instance.app_modules.set(
                AppModule.objects.filter(unique_id__in=module_ids, is_deleted=False)
            )
        if screen_ids is not None:
            instance.app_screens.set(
                UserScreen.objects.filter(unique_id__in=screen_ids, is_deleted=False)
            )
