from rest_framework import serializers
from app.models.masters.customer_masters.feedback import FeedBack
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.utils.hierarchy import flat_geo_display


class FeedBackSerializer(serializers.ModelSerializer):
    # Write the customer's unique_id as `customer`; read it back as
    # `customer_id` (a plain unique_id column, no DB relation).
    customer = serializers.CharField(write_only=True)
    customer_id = serializers.CharField(read_only=True)
    customer_name = serializers.SerializerMethodField(read_only=True)
    location_name = serializers.SerializerMethodField(read_only=True)
    location_level = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FeedBack
        fields = "__all__"

    def validate_customer(self, value):
        if value in (None, ""):
            raise serializers.ValidationError("Customer is required")
        if not CustomerCreation.objects.filter(unique_id=str(value)).exists():
            raise serializers.ValidationError("Invalid customer reference")
        return str(value)

    def validate(self, attrs):
        if "customer" in attrs:
            attrs["customer_id"] = attrs.pop("customer")
        return attrs

    def _customer(self, obj):
        cache = self.context.setdefault("_customers", {})
        if obj.customer_id not in cache:
            cache[obj.customer_id] = obj.customer
        return cache[obj.customer_id]

    def get_customer_name(self, obj):
        return getattr(self._customer(obj), "customer_name", None)

    def get_location_name(self, obj):
        customer = self._customer(obj)
        return flat_geo_display(customer)[0] if customer else None

    def get_location_level(self, obj):
        customer = self._customer(obj)
        return flat_geo_display(customer)[1] if customer else None

