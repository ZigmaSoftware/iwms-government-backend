from rest_framework import serializers
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.masters.waste_masters.property import Property
from app.validators.unique_name_validator import unique_name_validator


class SubPropertySerializer(serializers.ModelSerializer):
    # dropdown filtered only to active and not-deleted properties
    property_id = serializers.PrimaryKeyRelatedField(
        queryset=Property.objects.filter(is_active=True, is_deleted=False),
    )

    property_name = serializers.CharField(
        source="property_id.property_name",
        read_only=True
    )

    class Meta:
        model = SubProperty
        fields = "__all__"
        read_only_fields = ["unique_id"]
        validators = []

    def validate(self, attrs):
        return unique_name_validator(
            Model=SubProperty,
            name_field="sub_property_name",
            scope_fields=["property_id"]
        )(self, attrs)
