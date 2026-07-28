from rest_framework import serializers


def validate_unique_order_no(model_class, parent_field, parent_value, order_no, instance=None, error_message="This order number already exists."):
    """Ensure `order_no` is unique among siblings sharing `parent_field=parent_value`."""
    if order_no is None or parent_value is None:
        return

    queryset = model_class.objects.filter(**{parent_field: parent_value, "order_no": order_no, "is_deleted": False})
    if instance is not None:
        queryset = queryset.exclude(unique_id=instance.unique_id)

    if queryset.exists():
        raise serializers.ValidationError({"order_no": error_message})
