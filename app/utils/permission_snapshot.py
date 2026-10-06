"""
One User Access Audit record per access save.

Ported from the private backend and re-keyed onto this codebase's grants:
there is no Company/Project here, so grants are owned by a local body (plus
role ids and permission_owner_kind) or by one staff member
(permission_owner_kind="staff"), not by a company.

Every screen that writes permissions snapshots the access before and after a
successful write request and stores ONE PermissionAuditLog row per owner it
changed (old_permissions / new_permissions), along with the HTTP method:

* LOCAL_BODY_SCREEN - a local body's baseline grants (screens/actions,
  column visibility, dashboard widgets) for one role / owner kind.
* ROLE_SCREEN       - role-keyed grants with no local body
  (permissions/assign).
* STAFF_ACCESS      - one staff member's personal grants (Staff Access
  Configuration): their staff-owned screen/column/widget rows plus the
  mobile apps ticked on their StaffAccessConfiguration.
* CUSTOMER_ACCESS   - one customer's apps and citizen app screens.

A snapshot stores names as well as ids, so the trail stays readable after a
screen or action is renamed or removed:

    {
      "app_modules": [{"id": "...", "name": "Driver"}],
      "modules": [
        {"id": "MS-1", "name": "masters", "screens": [
          {"id": "US-1", "name": "wards",
           "actions": [{"id": "ACT-1", "name": "add"}, ...],
           "columns": [{"id": "COL-1", "name": "Ward Name", "state": "READ_ONLY"}]}
        ]}
      ],
      "widgets": [{"id": "trip_summary", "name": "Trip Summary"}]
    }

Customer screens carry no actions: the screen itself is the grant. A column
counts as granted in every field_permission_state except HIDDEN, so changing
its state shows as the old state revoked and the new one granted.
"""

import contextvars
import logging

from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn

logger = logging.getLogger(__name__)

EMPTY_SNAPSHOT = {"app_modules": [], "modules": [], "widgets": []}

LOCAL_BODY_LEVELS = (
    "corporation",
    "municipality",
    "town_panchayat",
    "panchayat_union",
    "panchayat",
)

ROLE_FIELDS = (
    "usertype_id",
    "staffusertype_id",
    "contractorusertype_id",
    "governmentusertype_id",
)

# Owner of a local-body / role grant, in the order it is stored in a scope
# key: ("LOCAL_BODY_SCREEN" | "ROLE_SCREEN", *these values).
SCOPE_FIELDS = (
    "state_id",
    "district_id",
    "area_type_id",
    "local_body_type",
    "local_body_id",
    "permission_owner_kind",
    *ROLE_FIELDS,
)

# Set while an audited request runs, so the per-grant post_save signal does
# not also log every row the snapshot row already covers.
_snapshot_audit_active = contextvars.ContextVar("permission_snapshot_audit", default=False)


def snapshot_audit_active():
    return _snapshot_audit_active.get()


# ------------------------------------------------------------------
# Snapshot <-> grant keys
# ------------------------------------------------------------------

def _names(model, ids, name_field):
    ids = [i for i in ids if i]
    if not ids:
        return {}
    return dict(
        model.objects.filter(unique_id__in=ids).values_list("unique_id", name_field)
    )


def _app_modules(ids):
    ids = [i for i in dict.fromkeys(ids) if i]
    names = _names(AppModule, ids, "label")
    return [{"id": i, "name": names.get(i) or i} for i in ids]


def widget_label(widget_name):
    return str(widget_name or "").replace("_", " ").strip().title() or "-"


def _build_modules(actions=(), columns=(), screens=(), modules=()):
    """actions: (userscreen_id, action_id); columns: (userscreen_id,
    column_id, state); screens: userscreen ids granted as a whole; modules:
    mainscreen ids granted as a whole. The main screen comes from the
    screen, which always knows it."""
    actions, columns, screens, modules = (
        list(actions), list(columns), list(screens), list(modules)
    )
    screen_ids = {a[0] for a in actions} | {c[0] for c in columns} | set(screens)
    screen_rows = {
        row["unique_id"]: row
        for row in UserScreen.objects.filter(unique_id__in=screen_ids).values(
            "unique_id", "userscreen_name", "mainscreen_id", "order_no"
        )
    }
    module_ids = set(modules) | {
        (screen_rows.get(sid) or {}).get("mainscreen_id") for sid in screen_ids
    }
    module_rows = {
        row["unique_id"]: row
        for row in MainScreen.objects.filter(
            unique_id__in={m for m in module_ids if m}
        ).values("unique_id", "mainscreen_name", "order_no")
    }
    action_names = _names(UserScreenAction, {a[1] for a in actions}, "action_name")
    column_names = _names(UserScreenColumn, {c[1] for c in columns}, "display_name")

    tree = {mid: {} for mid in modules}

    def screen_entry(sid):
        mid = (screen_rows.get(sid) or {}).get("mainscreen_id")
        return tree.setdefault(mid, {}).setdefault(sid, {"actions": [], "columns": []})

    for sid in screens:
        screen_entry(sid)
    for sid, action_id in actions:
        items = screen_entry(sid)["actions"]
        if all(i["id"] != action_id for i in items):
            items.append({"id": action_id, "name": action_names.get(action_id) or action_id})
    for sid, column_id, state in columns:
        items = screen_entry(sid)["columns"]
        if all((i["id"], i["state"]) != (column_id, state) for i in items):
            items.append({
                "id": column_id,
                "name": column_names.get(column_id) or column_id,
                "state": state,
            })

    def module_order(mid):
        row = module_rows.get(mid) or {}
        return (row.get("order_no") or 0, row.get("mainscreen_name") or mid or "")

    def screen_order(sid):
        row = screen_rows.get(sid) or {}
        return (row.get("order_no") or 0, row.get("userscreen_name") or sid or "")

    return [
        {
            "id": mid,
            "name": (module_rows.get(mid) or {}).get("mainscreen_name") or mid or "-",
            "screens": [
                {
                    "id": sid,
                    "name": (screen_rows.get(sid) or {}).get("userscreen_name") or sid or "-",
                    "actions": sorted(tree[mid][sid]["actions"], key=lambda a: a["name"]),
                    "columns": sorted(
                        tree[mid][sid]["columns"], key=lambda c: (c["name"], c["state"])
                    ),
                }
                for sid in sorted(tree[mid], key=screen_order)
            ],
        }
        for mid in sorted(tree, key=module_order)
    ]


def snapshot_keys(snapshot):
    """Every individual grant in a snapshot, as comparable keys."""
    snapshot = snapshot or EMPTY_SNAPSHOT
    keys = {("app", m["id"]) for m in snapshot.get("app_modules") or []}
    keys.update(("widget", w["id"]) for w in snapshot.get("widgets") or [])
    for module in snapshot.get("modules") or []:
        if not module.get("screens"):
            keys.add(("module", module["id"]))
        for screen in module.get("screens") or []:
            actions = screen.get("actions") or []
            columns = screen.get("columns") or []
            keys.update(("action", screen["id"], a["id"]) for a in actions)
            keys.update(("column", screen["id"], c["id"], c.get("state")) for c in columns)
            if not actions and not columns:
                keys.add(("screen", screen["id"]))
    return keys


def snapshot_from_keys(keys):
    """Inverse of snapshot_keys: rebuild a named snapshot from grant keys."""
    keys = set(keys)
    return {
        "app_modules": _app_modules(sorted(k[1] for k in keys if k[0] == "app")),
        "modules": _build_modules(
            actions=[(k[1], k[2]) for k in keys if k[0] == "action"],
            columns=[(k[1], k[2], k[3]) for k in keys if k[0] == "column"],
            screens=[k[1] for k in keys if k[0] == "screen"],
            modules=[k[1] for k in keys if k[0] == "module"],
        ),
        "widgets": [
            {"id": name, "name": widget_label(name)}
            for name in sorted(k[1] for k in keys if k[0] == "widget")
        ],
    }


def changed_module_ids(before, after):
    """Main screens whose grants differ between two snapshots."""
    changed = snapshot_keys(before) ^ snapshot_keys(after)
    ids = []
    for snapshot in (after, before):
        for module in (snapshot or {}).get("modules") or []:
            if module["id"] in ids:
                continue
            if snapshot_keys({"modules": [module]}) & changed:
                ids.append(module["id"])
    return ids


# ------------------------------------------------------------------
# Live permission state
# ------------------------------------------------------------------

def _scope_for(row):
    """The owner a permission row belongs to: one staff member for
    staff-owned rows, otherwise the local body / role it is keyed by."""
    if row.get("permission_owner_kind") == "staff" and row.get("staff_id"):
        return ("STAFF_ACCESS", row["staff_id"])
    source = "LOCAL_BODY_SCREEN" if row.get("local_body_id") else "ROLE_SCREEN"
    return (source, *(row.get(f) for f in SCOPE_FIELDS))


def permission_state():
    """{scope: grant keys} for every live screen/action, column and
    dashboard-widget permission, plus every staff member's app modules."""
    from app.models.superadmin.screen_management.dashboardwidgetpermission import (
        DashboardWidgetPermission,
    )
    from app.models.superadmin.screen_management.userscreencolumnpermission import (
        UserScreenColumnPermission,
    )
    from app.models.superadmin.screen_management.userscreenpermission import (
        UserScreenPermission,
    )
    from app.models.superadmin.staff_management.staff_access_configuration import (
        StaffAccessConfiguration,
        StaffAccessConfigurationPermission,
    )

    owner_fields = (*SCOPE_FIELDS, "staff_id")
    state = {}

    for row in UserScreenPermission.objects.filter(is_active=True, is_deleted=False).values(
        *owner_fields, "mainscreen_id", "userscreen_id", "userscreenaction_id"
    ):
        if row["userscreenaction_id"]:
            key = ("action", row["userscreen_id"], row["userscreenaction_id"])
        elif row["userscreen_id"]:
            key = ("screen", row["userscreen_id"])
        else:
            key = ("module", row["mainscreen_id"])
        state.setdefault(_scope_for(row), set()).add(key)

    hidden = UserScreenColumnPermission.HIDDEN
    for row in (
        UserScreenColumnPermission.objects.filter(is_active=True, is_deleted=False)
        .exclude(field_permission_state=hidden)
        .values(*owner_fields, "userscreen_id", "column_id", "field_permission_state")
    ):
        state.setdefault(_scope_for(row), set()).add(
            ("column", row["userscreen_id"], row["column_id"], row["field_permission_state"])
        )

    for row in DashboardWidgetPermission.objects.filter(
        is_active=True, is_deleted=False, is_enabled=True
    ).values(*owner_fields, "widget_name"):
        state.setdefault(_scope_for(row), set()).add(("widget", row["widget_name"]))

    configs = {}
    for config_id, staff_id, module_ids in StaffAccessConfiguration.objects.filter(
        is_deleted=False
    ).values_list("unique_id", "staff_id", "app_module_ids"):
        configs[config_id] = staff_id
        state.setdefault(("STAFF_ACCESS", staff_id), set()).update(
            ("app", m) for m in (module_ids or []) if m
        )
    for config_id, userscreen_id, action_id in StaffAccessConfigurationPermission.objects.filter(
        is_deleted=False, staff_access_configuration_id__in=list(configs)
    ).values_list("staff_access_configuration_id", "userscreen_id", "userscreenaction_id"):
        state[("STAFF_ACCESS", configs[config_id])].add(("action", userscreen_id, action_id))

    # An owner with nothing left is the same as no owner at all.
    return {scope: keys for scope, keys in state.items() if keys}


# ------------------------------------------------------------------
# Writing rows
# ------------------------------------------------------------------

def request_actor_id(request):
    """staff_unique_id for staff, otherwise the platform user's unique_id."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None
    staff_id = getattr(user, "staff_unique_id", None) or getattr(
        getattr(user, "staff", None), "staff_unique_id", None
    )
    return staff_id or getattr(user, "unique_id", None) or None


def flat_geo(obj):
    """state/district/area_type plus the one local body a flat-geo record
    (Staffcreation, CustomerCreation) sits in."""
    if obj is None:
        return {}
    geo = {
        "state_id": getattr(obj, "state_id", None) or None,
        "district_id": getattr(obj, "district_id", None) or None,
        "area_type_id": getattr(obj, "area_type_id", None) or None,
    }
    for level in LOCAL_BODY_LEVELS:
        value = getattr(obj, f"{level}_id", None)
        if value:
            geo["local_body_type"] = level
            geo["local_body_id"] = value
            break
    return geo


def write_access_audit(*, source, request, before, after, action_type, **fields):
    """Store one audit row for a save, unless it changed nothing. `fields`
    are the owner columns (target_id, staff_id, geo, role ids...)."""
    old_keys, new_keys = snapshot_keys(before), snapshot_keys(after)
    if old_keys == new_keys and action_type != "DELETED":
        return None
    modules = changed_module_ids(before, after)
    try:
        return PermissionAuditLog.objects.create(
            source=source,
            updated_by_id=request_actor_id(request),
            http_method=(getattr(request, "method", "") or "").upper() or None,
            old_permissions=before,
            new_permissions=after,
            # A save that touched one main screen keeps it filterable by
            # main screen, like the per-grant rows.
            mainscreen_id=modules[0] if len(modules) == 1 else None,
            is_active=bool(new_keys),
            is_deleted=action_type == "DELETED",
            previous_is_active=bool(old_keys),
            previous_is_deleted=False,
            action_type=action_type,
            **fields,
        )
    except Exception:
        logger.exception("Failed to write PermissionAuditLog for %s", source)
        return None


def _scope_fields(scope):
    """Owner columns for a scope key from permission_state()."""
    source = scope[0]
    if source == "STAFF_ACCESS":
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        staff_id = scope[1]
        staff = Staffcreation.objects.filter(staff_unique_id=staff_id).first()
        return {
            "target_id": staff_id,
            "staff_id": staff_id,
            "permission_owner_kind": "staff",
            "governmentusertype_id": getattr(staff, "governmentusertype_id", None),
            **flat_geo(staff),
        }
    return dict(zip(SCOPE_FIELDS, scope[1:]))


def write_permission_audits(request, before, after):
    """One row per owner whose grants differ between two states."""
    for scope in sorted(set(before) | set(after), key=lambda k: tuple(str(p) for p in k)):
        old_keys, new_keys = before.get(scope, set()), after.get(scope, set())
        if old_keys == new_keys:
            continue
        write_access_audit(
            source=scope[0],
            request=request,
            before=snapshot_from_keys(old_keys),
            after=snapshot_from_keys(new_keys),
            action_type=(
                "CREATED" if not old_keys else "DELETED" if not new_keys else "UPDATED"
            ),
            **_scope_fields(scope),
        )


class PermissionSnapshotAuditMixin:
    """For views that write screen/column/widget permissions or a staff
    member's app access: one User Access Audit row per owner (local body +
    role, or staff member) that a successful write request changed.

    Several of these endpoints write through queryset.update() /
    bulk_create() / update_or_create(), which fire no reliable per-row
    signal, so the whole permission state is compared instead."""

    AUDITED_METHODS = ("POST", "PUT", "PATCH", "DELETE")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method in self.AUDITED_METHODS:
            self._permission_state_before = permission_state()
            self._permission_audit_token = _snapshot_audit_active.set(True)

    def finalize_response(self, request, response, *args, **kwargs):
        before = self.__dict__.pop("_permission_state_before", None)
        token = self.__dict__.pop("_permission_audit_token", None)
        try:
            if before is not None and getattr(response, "status_code", 500) < 400:
                write_permission_audits(request, before, permission_state())
        except Exception:
            logger.exception("Failed to write permission snapshot audit")
        finally:
            if token is not None:
                _snapshot_audit_active.reset(token)
        return super().finalize_response(request, response, *args, **kwargs)


# ------------------------------------------------------------------
# Customer Access Configuration
# ------------------------------------------------------------------

def customer_access_snapshot(config):
    """A customer's apps and citizen app screens."""
    if not config or config.is_deleted:
        return EMPTY_SNAPSHOT
    return {
        "app_modules": _app_modules(list(config.app_module_ids or [])),
        "modules": _build_modules(screens=[s for s in (config.app_screen_ids or []) if s]),
        "widgets": [],
    }


def write_customer_access_audit(request, config, before, after, action_type):
    from app.models.masters.customer_masters.customercreation import CustomerCreation

    customer = CustomerCreation.objects.filter(unique_id=config.customer_id).first()
    return write_access_audit(
        source="CUSTOMER_ACCESS",
        request=request,
        before=before,
        after=after,
        action_type=action_type,
        target_id=config.customer_id,
        **flat_geo(customer),
    )
