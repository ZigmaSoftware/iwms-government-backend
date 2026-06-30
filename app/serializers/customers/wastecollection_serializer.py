from rest_framework import serializers
from app.models.customers.wastecollection import WasteCollection
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment


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
            # fallback: pk
            try:
                return self.get_queryset().get(pk=int(data))
            except (ValueError, TypeError, CustomerCreation.DoesNotExist):
                raise serializers.ValidationError("Invalid customer reference")


class WasteCollectionSerializer(serializers.ModelSerializer):
    customer = CustomerField(
        slug_field="unique_id",
        queryset=CustomerCreation.objects.all(),
        write_only=True,
    )
    # Expose customer unique identifier as `customer_id`
    customer_id = serializers.CharField(
        source="customer.unique_id", read_only=True
    )
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    # Geography is now the customer's single hierarchy node.
    location_name = serializers.CharField(source="customer.location_node.name", read_only=True, default=None)
    location_level = serializers.CharField(source="customer.location_node.level.name", read_only=True, default=None)

    trip_assignment_id = serializers.SlugRelatedField(
        slug_field="unique_id",
        queryset=DailyTripAssignment.objects.filter(is_deleted=False),
        required=False,
        allow_null=True,
    )
    trip_assignment_display = serializers.CharField(
        source="trip_assignment_id.unique_id", read_only=True, default=None
    )

    class Meta:
        model = WasteCollection
        fields = "__all__"
        extra_kwargs = {
            "customer": {"write_only": True},
        }
