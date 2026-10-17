from rest_framework import serializers
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.masters.waste_masters.property import Property
from app.validators.unique_name_validator import unique_name_validator
from app.utils import ref_cache


class SubPropertySerializer(serializers.ModelSerializer):
    # Plain Property unique_id (no DB relation); only active, not-deleted
    # properties are accepted.
    property_id = serializers.CharField()

    property_name = serializers.SerializerMethodField()

    def get_property_name(self, obj):
        return getattr(ref_cache.get(Property, obj.property_id, "unique_id"), "property_name", None)

    def validate_property_id(self, value):
        if not Property.objects.filter(
            unique_id=value, is_active=True, is_deleted=False
        ).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value

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
