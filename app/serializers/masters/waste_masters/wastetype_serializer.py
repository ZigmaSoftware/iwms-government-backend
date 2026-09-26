from rest_framework import serializers
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.core_modules.complaint_management.team_master import ComplaintTeam
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.utils import ref_cache


class WasteTypeSerializer(serializers.ModelSerializer):
    # Plain unique_id columns (no DB relation); exposed under the same
    # `default_team` / `default_priority` names the API always used.
    default_team = serializers.CharField(
        source="default_team_id", required=False, allow_null=True, allow_blank=True
    )
    default_priority = serializers.CharField(
        source="default_priority_id", required=False, allow_null=True, allow_blank=True
    )
    default_team_name = serializers.SerializerMethodField()
    default_priority_code = serializers.SerializerMethodField()

    class Meta:
        model = WasteType
        exclude = ["default_team_id", "default_priority_id"]

    def get_default_team_name(self, obj):
        if not obj.default_team_id:
            return None
        return getattr(ref_cache.get(ComplaintTeam, obj.default_team_id), "team_name", None)

    def get_default_priority_code(self, obj):
        if not obj.default_priority_id:
            return None
        return getattr(ref_cache.get(ComplaintPriority, obj.default_priority_id), "priority_code", None)

    def validate_default_team(self, value):
        if not value:
            return None
        if not ComplaintTeam.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value

    def validate_default_priority(self, value):
        if not value:
            return None
        if not ComplaintPriority.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f'Invalid pk "{value}" - object does not exist.')
        return value
