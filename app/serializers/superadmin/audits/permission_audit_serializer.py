import importlib

from rest_framework import serializers

from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.userscreenpermission import LocalBodyType
from app.utils import ref_cache
from app.utils.permission_snapshot import snapshot_keys

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
    for field in ("name", f"{local_body_type}_name", "union_name"):
        value = getattr(instance, field, None)
        if value:
            return value
    return str(instance)


class PermissionAuditLogSerializer(serializers.ModelSerializer):
    """Read-only view of a permission change with its ids resolved to
    display names. Two kinds of row share the table:

    * access-save rows (source LOCAL_BODY_SCREEN / ROLE_SCREEN /
      STAFF_ACCESS / CUSTOMER_ACCESS) hold the whole access before and after
      one save (old_permissions / new_permissions) and get granted/revoked
      counts plus the modules the save changed;
    * per-grant rows (GRANT_CHANGE, every row from before saves were
      snapshotted) describe one screen/action and leave those blank.

    The list leaves the snapshots out (see PermissionAuditLogListSerializer);
    the detail endpoint returns them."""

    usertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    staffusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    contractorusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    governmentusertype_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    mainscreen_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    userscreen_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    userscreenaction_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    updated_by_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    source_label = serializers.CharField(source="get_source_display", read_only=True)
    target_name = serializers.SerializerMethodField()
    local_body_name = serializers.SerializerMethodField()
    staffusertype_name = serializers.SerializerMethodField()
    governmentusertype_name = serializers.SerializerMethodField()
    mainscreen_name = serializers.SerializerMethodField()
    userscreen_name = serializers.SerializerMethodField()
    userscreenaction_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()
    role_display = serializers.SerializerMethodField()
    granted_count = serializers.SerializerMethodField()
    revoked_count = serializers.SerializerMethodField()
    changed_modules = serializers.SerializerMethodField()

    class Meta:
        model = PermissionAuditLog
        fields = [
            "id",
            "source",
            "source_label",
            "target_id",
            "target_name",
            "usertype_id",
            "staffusertype_id",
            "staffusertype_name",
            "contractorusertype_id",
            "governmentusertype_id",
            "governmentusertype_name",
            "permission_owner_kind",
            "state_id",
            "district_id",
            "area_type_id",
            "local_body_type",
            "local_body_id",
            "local_body_name",
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
            "http_method",
            "old_permissions",
            "new_permissions",
            "granted_count",
            "revoked_count",
            "changed_modules",
            "timestamp",
        ]
        read_only_fields = fields

    def _lookup(self, dotted, value, field="unique_id"):
        if not value:
            return None
        module_path, class_name = dotted.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    def get_staffusertype_name(self, obj):
        return getattr(obj.staffusertype, "name", None)

    def get_governmentusertype_name(self, obj):
        return getattr(obj.governmentusertype, "name", None)

    def get_mainscreen_name(self, obj):
        return getattr(obj.mainscreen, "mainscreen_name", None)

    def get_userscreen_name(self, obj):
        return getattr(obj.userscreen, "userscreen_name", None)

    def get_userscreenaction_name(self, obj):
        return getattr(obj.userscreenaction, "action_name", None)

    def get_local_body_name(self, obj):
        if not (obj.local_body_type and obj.local_body_id):
            return None
        cache = self.__dict__.setdefault("_local_body_cache", {})
        key = (obj.local_body_type, obj.local_body_id)
        if key not in cache:
            cache[key] = _resolve_local_body_name(*key) or obj.local_body_id
        return cache[key]

    def get_updated_by_name(self, obj):
        # updated_by_id is a staff member's staff_unique_id, or a platform
        # User's unique_id. Rows from before the actor was captured leave
        # it blank.
        if not obj.updated_by_id:
            return None
        staff = obj.updated_by
        if staff is not None:
            return getattr(staff, "employee_name", None) or obj.updated_by_id
        user = self._lookup(
            "app.models.superadmin_masters.auth_user.User", obj.updated_by_id
        )
        return getattr(user, "username", None) or obj.updated_by_id

    def get_target_name(self, obj):
        """Who the access was granted to: the staff member or customer for
        a person's access, otherwise the local body / role it is keyed by."""
        if obj.source == "STAFF_ACCESS":
            staff = self._lookup(
                "app.models.superadmin.staff_management.staffcreation.Staffcreation",
                obj.target_id,
                field="staff_unique_id",
            )
            return getattr(staff, "employee_name", None) or obj.target_id
        if obj.source == "CUSTOMER_ACCESS":
            customer = self._lookup(
                "app.models.masters.customer_masters.customercreation.CustomerCreation",
                obj.target_id,
            )
            return getattr(customer, "customer_name", None) or obj.target_id
        return self.get_role_display(obj)

    def get_role_display(self, obj):
        """Best available "who this grant applies to" label, falling back
        through the role hierarchy so a row is never blank just because it
        wasn't a StaffUserType-based grant."""
        if obj.staffusertype_id:
            return getattr(obj.staffusertype, "name", None)
        if obj.contractorusertype_id:
            return getattr(obj.contractorusertype, "name", None)
        if obj.governmentusertype_id and obj.permission_owner_kind != "staff":
            return getattr(obj.governmentusertype, "name", None)
        if obj.usertype_id:
            return getattr(obj.usertype, "name", None)

        if obj.permission_owner_kind == "staff" and obj.staff_id:
            return f"Staff override ({obj.staff_id})"

        if obj.local_body_type and obj.local_body_id:
            label = self.get_local_body_name(obj)
            return f"{obj.local_body_type.replace('_', ' ').title()}: {label}"

        return None

    # Access-save rows (old/new snapshots) summarise what the save changed;
    # per-grant rows leave these blank.

    def _diff(self, obj):
        if obj.old_permissions is None and obj.new_permissions is None:
            return None
        cache = self.__dict__.setdefault("_diff_cache", {})
        if obj.pk not in cache:
            old = snapshot_keys(obj.old_permissions)
            new = snapshot_keys(obj.new_permissions)
            cache[obj.pk] = (new - old, old - new)
        return cache[obj.pk]

    def get_granted_count(self, obj):
        diff = self._diff(obj)
        return len(diff[0]) if diff else None

    def get_revoked_count(self, obj):
        diff = self._diff(obj)
        return len(diff[1]) if diff else None

    def get_changed_modules(self, obj):
        """Names of the modules the save changed ("App Access" for the apps,
        "Dashboard Widgets" for widgets)."""
        diff = self._diff(obj)
        if not diff:
            return None
        changed = diff[0] | diff[1]
        names = []
        if any(key[0] == "app" for key in changed):
            names.append("App Access")
        if any(key[0] == "widget" for key in changed):
            names.append("Dashboard Widgets")
        seen = set()
        for snapshot in (obj.new_permissions, obj.old_permissions):
            for module in (snapshot or {}).get("modules") or []:
                if module["name"] in seen:
                    continue
                if snapshot_keys({"modules": [module]}) & changed:
                    seen.add(module["name"])
                    names.append(module["name"])
        return names


class PermissionAuditLogListSerializer(PermissionAuditLogSerializer):
    """List rows: the counts and changed modules, without the two full
    snapshots (the detail endpoint returns those)."""

    class Meta(PermissionAuditLogSerializer.Meta):
        fields = [
            f
            for f in PermissionAuditLogSerializer.Meta.fields
            if f not in ("old_permissions", "new_permissions")
        ]
        read_only_fields = fields
