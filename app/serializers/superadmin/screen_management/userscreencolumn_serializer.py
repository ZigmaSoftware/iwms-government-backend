# =========================================================
# serializers/screen_managements/userscreencolumn_serializer.py
# =========================================================

from rest_framework import serializers

from app.models.superadmin.screen_management.userscreencolumn import (
    UserScreenColumn
)
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.utils import ref_cache


class UserScreenColumnSerializer(serializers.ModelSerializer):

    userscreen_id = serializers.CharField()
    userscreen_name = serializers.SerializerMethodField()
    id = serializers.CharField(source="unique_id", read_only=True)
    fieldName = serializers.CharField(source="field_name", read_only=True)
    displayName = serializers.CharField(source="display_name", read_only=True)
    dataType = serializers.CharField(source="data_type", read_only=True)
    dbColumn = serializers.CharField(source="db_column", read_only=True)

    class Meta:

        model = UserScreenColumn

        fields = "__all__"

    def get_userscreen_name(self, obj):
        return getattr(obj.userscreen, "userscreen_name", None)
