import importlib

from rest_framework import serializers

from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.userscreenpermission import LocalBodyType
from app.utils import ref_cache

LOCAL_BODY_MODELS = {
    "corporation": "app.models.masters.corporation.Corporation",
    "municipality": "app.models.masters.municipality.Municipality",
    "panchayat": "app.models.masters.panchayat.Panchayat",
    "town_panchayat": "app.models.masters.town_panchayat.TownPanchayat",
    "panchayat_union": "app.models.masters.panchayat_union.PanchayatUnion",
}


def _resolve_local_body_name(local_body_type, local_body_id):
    dotted = LOCAL_BODY_MODELS.get(local_body_type)
    if not dotted or not local_body_id:
        return None
    module_path, class_name = dotted.rsplit(".", 1)
    model = getattr(importlib.import_module(module_path), class_name)
    instance = model.objects.filter(unique_id=local_body_id).first()
    if not instance:
        return None
    for field in ("name", f"{local_body_type}_name"):
        value = getattr(instance, field, None)
        if value:
            return value
    return str(instance)


class PermissionAuditLogSerializer(serializers.ModelSerializer):
    usertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    staffusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contractorusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    governmentusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    mainscreen_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    userscreen_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    userscreenaction_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    updated_by_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    staffusertype_name = serializers.SerializerMethodField()
    mainscreen_name = serializers.SerializerMethodField()
    userscreen_name = serializers.SerializerMethodField()
    userscreenaction_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    role_display = serializers.SerializerMethodField()

    class Meta:
        model = PermissionAuditLog
        fields = [
            "id",
            "usertype_id",
            "staffusertype_id",
            "staffusertype_name",
            "contractorusertype_id",
            "governmentusertype_id",
            "permission_owner_kind",
            "local_body_type",
            "local_body_id",
            "staff_id",
            "role_display",
            "mainscreen_id",
            "mainscreen_name",
            "userscreen_id",
            "userscreen_name",
            "userscreenaction_id",
            "userscreenaction_name",
            "updated_by_id",
            "updated_by_name",
            "is_active",
            "is_deleted",
            "previous_is_active",
            "previous_is_deleted",
            "action_type",
            "timestamp",
        ]
        read_only_fields = fields

    def get_staffusertype_name(self, obj):
        return getattr(obj.staffusertype, "name", None)

    def get_mainscreen_name(self, obj):
        return getattr(obj.mainscreen, "mainscreen_name", None)

    def get_userscreen_name(self, obj):
        return getattr(obj.userscreen, "userscreen_name", None)

    def get_userscreenaction_name(self, obj):
        return getattr(obj.userscreenaction, "action_name", None)

    def get_updated_by_name(self, obj):
        return getattr(obj.updated_by, "employee_name", None)

    def get_role_display(self, obj):
        """Best available "who this grant applies to" label, falling back
        through the role hierarchy so a row is never blank just because it
        wasn't a StaffUserType-based grant."""
        if obj.staffusertype_id:
            return getattr(obj.staffusertype, "name", None)
        if obj.contractorusertype_id:
            return getattr(obj.contractorusertype, "name", None)
        if obj.governmentusertype_id:
            return getattr(obj.governmentusertype, "name", None)
        if obj.usertype_id:
            return getattr(obj.usertype, "name", None)

        if obj.permission_owner_kind == "staff" and obj.staff_id:
            return f"Staff override ({obj.staff_id})"

        if obj.local_body_type and obj.local_body_id:
            body_name = _resolve_local_body_name(obj.local_body_type, obj.local_body_id)
            label = body_name or obj.local_body_id
            return f"{obj.local_body_type.replace('_', ' ').title()}: {label}"

        return None
