from rest_framework import serializers

from app.models.masters.customer_masters.customer_notification import (
    CustomerNotification,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation


class CustomerNotificationSerializer(serializers.ModelSerializer):
    customer_unique_id = serializers.CharField(write_only=True, required=False)
    customer_id = serializers.CharField(read_only=True)
    # `customer` is a ref_cache-backed property (customer_id is a plain id).
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True, default=None)
    contact_no = serializers.CharField(source="customer.contact_no", read_only=True, default=None)
    username = serializers.CharField(source="customer.username", read_only=True, default=None)
    has_fcm_token = serializers.SerializerMethodField()

    class Meta:
        model = CustomerNotification
        fields = [
            "unique_id",
            "customer_id",
            "customer_unique_id",
            "customer_name",
            "contact_no",
            "username",
            "has_fcm_token",
            "last_tested_at",
            "last_test_sent",
            "last_test_message",
            "is_active",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "unique_id",
            "customer_id",
            "customer_name",
            "contact_no",
            "username",
            "has_fcm_token",
            "last_tested_at",
            "last_test_sent",
            "last_test_message",
            "created_at",
            "updated_at",
        ]

    def get_has_fcm_token(self, instance):
        return bool(getattr(instance.customer, "fcm_token", None))

    def validate(self, attrs):
        customer_id = self.initial_data.get("customer_unique_id") or self.initial_data.get(
            "customer_id"
        )
        if customer_id:
            customer = CustomerCreation.objects.filter(
                unique_id=customer_id,
                is_deleted=False,
                is_active=True,
            ).first()
            if not customer:
                raise serializers.ValidationError(
                    {"customer_unique_id": f"No active customer '{customer_id}'."}
                )
            attrs["resolved_customer"] = customer
        elif not self.instance:
            raise serializers.ValidationError(
                {"customer_unique_id": "This field is required."}
            )
        return attrs

    def create(self, validated_data):
        customer = validated_data.pop("resolved_customer")
        validated_data.pop("customer_unique_id", None)
        instance, _ = CustomerNotification.objects.update_or_create(
            customer_id=customer.unique_id,
            is_deleted=False,
            defaults={"is_active": True, "is_deleted": False},
        )
        return instance

    def update(self, instance, validated_data):
        customer = validated_data.pop("resolved_customer", None)
        validated_data.pop("customer_unique_id", None)
        if customer:
            instance.customer_id = customer.unique_id
        instance.save()
        return instance
