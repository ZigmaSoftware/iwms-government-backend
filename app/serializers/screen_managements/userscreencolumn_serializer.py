# =========================================================
# serializers/screen_managements/userscreencolumn_serializer.py
# =========================================================

from rest_framework import serializers

from app.models.screen_managements.userscreencolumn import (
    UserScreenColumn
)


class UserScreenColumnSerializer(serializers.ModelSerializer):

    userscreen_name = serializers.CharField(
        source="userscreen_id.userscreen_name",
        read_only=True
    )
    id = serializers.CharField(source="unique_id", read_only=True)
    fieldName = serializers.CharField(source="field_name", read_only=True)
    displayName = serializers.CharField(source="display_name", read_only=True)
    dataType = serializers.CharField(source="data_type", read_only=True)
    dbColumn = serializers.CharField(source="db_column", read_only=True)

    class Meta:

        model = UserScreenColumn

        fields = "__all__"
