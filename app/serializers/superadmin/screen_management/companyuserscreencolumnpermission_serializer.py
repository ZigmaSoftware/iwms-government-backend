from rest_framework import serializers

from app.models.superadmin.screen_management.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn
from app.models.superadmin.screen_management.companyuserscreenpermission import LocalBodyType
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.serializers.superadmin.screen_management.companyuserscreenpermission_serializer import (
    _resolve_local_body_model,
)


class CompanyUserScreenColumnPermissionSerializer(serializers.ModelSerializer):
    column_name = serializers.CharField(source="column_id.field_name", read_only=True)
    display_name = serializers.CharField(source="column_id.display_name", read_only=True)
    data_type = serializers.CharField(source="column_id.data_type", read_only=True)
    userscreen_name = serializers.CharField(source="userscreen_id.userscreen_name", read_only=True)
    can_view = serializers.BooleanField(read_only=True)

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
            "field_permission_state",
        ]


class UserScreenColumnPermissionWriteSerializer(serializers.Serializer):
    """
    Write serializer for create operations.
    Validates that column_id belongs to the given userscreen_id.
    """

    userscreen_id = serializers.CharField()
    column_id = serializers.CharField()

    state_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    stateId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    district_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    districtId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    area_type_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    areaTypeId = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    local_body_type = serializers.ChoiceField(
        choices=LocalBodyType.choices, required=False, allow_null=True, allow_blank=True,
    )
    localBodyType = serializers.ChoiceField(
        choices=LocalBodyType.choices, required=False, allow_null=True, allow_blank=True,
    )
    local_body_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    localBodyId = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    is_active = serializers.BooleanField(default=True)
    field_permission_state = serializers.ChoiceField(
        choices=CompanyUserScreenColumnPermission.FIELD_PERMISSION_STATE_CHOICES,
        required=False,
    )
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
        data["state_id"] = (data.get("state_id") or data.get("stateId") or "").strip() or None
        data["district_id"] = (data.get("district_id") or data.get("districtId") or "").strip() or None
        data["area_type_id"] = (data.get("area_type_id") or data.get("areaTypeId") or "").strip() or None
        data["local_body_type"] = (data.get("local_body_type") or data.get("localBodyType") or "").strip() or None
        data["local_body_id"] = (data.get("local_body_id") or data.get("localBodyId") or "").strip() or None

        if not data["local_body_type"] or not data["local_body_id"]:
            raise serializers.ValidationError({
                "local_body_id": "local_body_type and local_body_id are required. "
                                  "Field Permission is owned by the Local Body hierarchy."
            })

        if data["state_id"] and not State.objects.filter(unique_id=data["state_id"], is_deleted=False).exists():
            raise serializers.ValidationError({"state_id": "Invalid state"})
        if data["district_id"] and not District.objects.filter(unique_id=data["district_id"], is_deleted=False).exists():
            raise serializers.ValidationError({"district_id": "Invalid district"})
        if data["area_type_id"] and not AreaType.objects.filter(unique_id=data["area_type_id"], is_deleted=False).exists():
            raise serializers.ValidationError({"area_type_id": "Invalid area_type"})

        local_body_model = _resolve_local_body_model(data["local_body_type"])
        if not local_body_model:
            raise serializers.ValidationError({"local_body_type": "Invalid local_body_type"})
        if not local_body_model.objects.filter(unique_id=data["local_body_id"], is_deleted=False).exists():
            raise serializers.ValidationError({"local_body_id": "Invalid local_body_id for local_body_type"})

        if "field_permission_state" not in data:
            data["field_permission_state"] = (
                CompanyUserScreenColumnPermission.VISIBLE
                if data.get("is_active", True)
                else CompanyUserScreenColumnPermission.HIDDEN
            )
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
