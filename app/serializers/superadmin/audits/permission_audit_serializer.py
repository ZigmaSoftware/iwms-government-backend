import importlib

from rest_framework import serializers

from app.models.superadmin.audits.permission_audit import PermissionAuditLog

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
    staffusertype_name = serializers.CharField(source="staffusertype.name", read_only=True, default=None)
    mainscreen_name = serializers.CharField(source="mainscreen.mainscreen_name", read_only=True, default=None)
    userscreen_name = serializers.CharField(source="userscreen.userscreen_name", read_only=True, default=None)
    userscreenaction_name = serializers.CharField(source="userscreenaction.action_name", read_only=True, default=None)
    updated_by_name = serializers.CharField(source="updated_by.employee_name", read_only=True, default=None)
    role_display = serializers.SerializerMethodField()

    class Meta:
        model = PermissionAuditLog
        fields = [
            "id",
            "staffusertype",
            "staffusertype_name",
            "usertype",
            "contractorusertype",
            "governmentusertype",
            "permission_owner_kind",
            "local_body_type",
            "local_body_id",
            "staff_id",
            "role_display",
            "mainscreen",
            "mainscreen_name",
            "userscreen",
            "userscreen_name",
            "userscreenaction",
            "userscreenaction_name",
            "updated_by",
            "updated_by_name",
            "is_active",
            "is_deleted",
            "previous_is_active",
            "previous_is_deleted",
            "action_type",
            "timestamp",
        ]
        read_only_fields = fields

    def get_role_display(self, obj):
        """Best available "who this grant applies to" label, falling back
        through the role hierarchy so a row is never blank just because it
        wasn't a StaffUserType-based grant."""
        if obj.staffusertype_id:
            return obj.staffusertype.name
        if obj.contractorusertype_id:
            return obj.contractorusertype.name
        if obj.governmentusertype_id:
            return obj.governmentusertype.name
        if obj.usertype_id:
            return obj.usertype.name

        if obj.permission_owner_kind == "staff" and obj.staff_id:
            return f"Staff override ({obj.staff_id})"

        if obj.local_body_type and obj.local_body_id:
            body_name = _resolve_local_body_name(obj.local_body_type, obj.local_body_id)
            label = body_name or obj.local_body_id
            return f"{obj.local_body_type.replace('_', ' ').title()}: {label}"

        return None
