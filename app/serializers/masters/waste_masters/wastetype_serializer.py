from rest_framework import serializers
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.utils import ref_cache


class WasteTypeSerializer(serializers.ModelSerializer):
    # Plain unique_id column (no DB relation); exposed under the same
    # `default_priority` name the API always used.
    default_priority = serializers.CharField(
        source="default_priority_id", required=False, allow_null=True, allow_blank=True
    )
    default_priority_code = serializers.SerializerMethodField()

    class Meta:
        model = WasteType
        exclude = ["default_priority_id"]

    def get_default_priority_code(self, obj):
        if not obj.default_priority_id:
            return None
        return getattr(ref_cache.get(ComplaintPriority, obj.default_priority_id), "priority_code", None)

    def validate_default_priority(self, value):
        if not value:
            return None
        if not ComplaintPriority.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value
