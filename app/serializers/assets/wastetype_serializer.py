from rest_framework import serializers
from app.models.assets.wastetype import WasteType


class WasteTypeSerializer(serializers.ModelSerializer):
    default_team_name = serializers.CharField(source="default_team.team_name", read_only=True, default=None)
    default_priority_code = serializers.CharField(source="default_priority.priority_code", read_only=True, default=None)

    class Meta:
        model = WasteType
        fields = "__all__"
