from rest_framework import serializers
from app.models.customers.feedback import FeedBack
from app.models.customers.customercreation import CustomerCreation


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
    district_name = serializers.CharField(source="customer.district.name", read_only=True)
    state_name = serializers.CharField(source="customer.state.name", read_only=True)
    corporation_name = serializers.CharField(source="customer.corporation_id.corporation_name", read_only=True, default=None)
    municipality_name = serializers.CharField(source="customer.municipality_id.municipality_name", read_only=True, default=None)
    town_panchayat_name = serializers.CharField(source="customer.town_panchayat_id.town_panchayat_name", read_only=True, default=None)
    panchayat_union_name = serializers.CharField(source="customer.panchayat_union_id.union_name", read_only=True, default=None)
    panchayat_name = serializers.CharField(source="customer.panchayat_id.panchayat_name", read_only=True, default=None)

    class Meta:
        model = FeedBack
        fields = "__all__"
        extra_kwargs = {
            "customer": {"write_only": True},
        }
    
