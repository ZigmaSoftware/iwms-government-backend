from rest_framework import serializers

from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreencolumn import UserScreenColumn


class CompanyUserScreenColumnPermissionSerializer(serializers.ModelSerializer):
    column_name = serializers.CharField(source="column_id.field_name", read_only=True)
    display_name = serializers.CharField(source="column_id.display_name", read_only=True)
    data_type = serializers.CharField(source="column_id.data_type", read_only=True)
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)

    class Meta:
        model = CompanyUserScreenColumnPermission
        fields = "__all__"


# ---------------------------------------------------------------------------
# Dedicated column-permission API serializers
# ---------------------------------------------------------------------------

class UserScreenColumnPermissionSerializer(serializers.ModelSerializer):
    """
    Read serializer returning the frontend-facing clean format.
    Maps: unique_id → userscreencolumnpermission_id
          column_id  → userscreencolumn_id
          can_view   → is_active
    """

    userscreencolumnpermission_id = serializers.CharField(source="unique_id", read_only=True)
    userscreencolumn_id = serializers.CharField(source="column_id_id", read_only=True)
    column_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(source="can_view", read_only=True)
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)

    def get_column_name(self, obj):
        col = obj.column_id
        return (col.display_name or col.field_name) if col else ""

    class Meta:
        model = CompanyUserScreenColumnPermission
        fields = [
            "userscreen_name",
            "userscreencolumnpermission_id",
            "userscreencolumn_id",
            "column_name",
            "is_active",
        ]


class UserScreenColumnPermissionWriteSerializer(serializers.Serializer):
    """
    Write serializer for create operations.
    Validates that column_id belongs to the given userscreen_id.
    """

    userscreen_id = serializers.CharField()
    column_id = serializers.CharField()
    staffusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contractorusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contractorUserTypeId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    usertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    is_active = serializers.BooleanField(default=True)
    order_no = serializers.IntegerField(default=1, required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_userscreen_id(self, value):
        if not UserScreen.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError("Invalid userscreen_id.")
        return value

    def validate_column_id(self, value):
        if not UserScreenColumn.objects.filter(unique_id=value, is_deleted=False).exists():
            raise serializers.ValidationError("Invalid column_id.")
        return value

    def validate(self, data):
        data["contractorusertype_id"] = (
            data.get("contractorusertype_id")
            or data.get("contractorUserTypeId")
            or ""
        ).strip() or None
        userscreen_id = data.get("userscreen_id")
        column_id = data.get("column_id")
        if userscreen_id and column_id:
            if not UserScreenColumn.objects.filter(
                unique_id=column_id,
                userscreen_id_id=userscreen_id,
                is_deleted=False,
            ).exists():
                raise serializers.ValidationError(
                    {"column_id": "Column does not belong to the specified userscreen."}
                )
        return data
