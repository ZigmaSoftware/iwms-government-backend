from rest_framework import serializers
from app.models.customers.feedback import FeedBack
from app.models.customers.customercreation import CustomerCreation
from app.utils.hierarchy import flat_geo_display


class CustomerField(serializers.SlugRelatedField):
    """Accept customer unique_id or PK, serialize as unique_id."""

    def to_representation(self, value):
        return value.unique_id if value else None

    def to_internal_value(self, data):
        if data in [None, ""]:
            raise serializers.ValidationError("Customer is required")
        # try unique_id
        try:
            return self.get_queryset().get(unique_id=str(data))
        except CustomerCreation.DoesNotExist:
            # fallback to pk
            try:
                return self.get_queryset().get(pk=int(data))
            except (ValueError, TypeError, CustomerCreation.DoesNotExist):
                raise serializers.ValidationError("Invalid customer reference")


class FeedBackSerializer(serializers.ModelSerializer):
    customer = CustomerField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.all(),
        write_only=True,
    )
    # Expose customer identifier as `customer_id`
    customer_id = serializers.CharField(source="customer.unique_id", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    location_name = serializers.SerializerMethodField(read_only=True)
    location_level = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FeedBack
        fields = "__all__"
        extra_kwargs = {
            "customer": {"write_only": True},
        }

    def get_location_name(self, obj):
        name, _ = flat_geo_display(obj.customer)
        return name

    def get_location_level(self, obj):
        _, level = flat_geo_display(obj.customer)
        return level

