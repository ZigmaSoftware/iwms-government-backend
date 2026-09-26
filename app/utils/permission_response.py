import hashlib
import json
import re

from django.utils import timezone

from app.models.superadmin.screen_management.userscreencolumnpermission import (
    UserScreenColumnPermission,
)
from app.models.superadmin.screen_management.userscreenpermission import UserScreenPermission
from app.models.superadmin.screen_management.dashboardwidgetpermission import DashboardWidgetPermission


ACTION_KEYS = ("view", "add", "edit", "delete")

APP_SURFACE_CONFIG = {
    "citizen": {
        "label": "Citizen",
        "route": "/citizen/home",
    },
    "operator": {
        "label": "Operator",
        "route": "/operator/home",
    },
    "driver": {
        "label": "Driver",
        "route": "/driver/home",
    },
    "supervisor": {
        "label": "Supervisor",
        "route": "/supervisor/home",
    },
    "admin": {
        "label": "Admin",
        "route": "/admin/home",
    },
}


def base_action_map():
    return {action: False for action in ACTION_KEYS}


def merge_permission_maps(base, extra):
    merged = {
        module: {
            screen: list(actions)
            for screen, actions in screens.items()
        }
        for module, screens in (base or {}).items()
    }
    for module_name, screens in (extra or {}).items():
        module_perms = merged.setdefault(module_name, {})
        for screen_name, actions in screens.items():
            existing = set(module_perms.get(screen_name, []))
            module_perms[screen_name] = sorted(existing.union(actions))
    return merged


def role_default_permissions(role_name):
    normalized = normalize_permission_key(role_name)
    if not normalized:
        return {}

    if normalized.endswith("driver") or normalized.endswith("operator"):
        return {
            "transport-masters": {
                "vehicle-creation": ["view"],
            },
            "customers": {
                "customercreations": ["view"],
            },
            "schedule-operations": {
                "daily-trip-assignments": ["view"],
                "vehicle-breakdowns": ["view", "add", "edit"],
                "daily-trip-logs": ["view"],
            },
        }

    if normalized.endswith("supervisor"):
        return {
            "transport-masters": {
                "vehicle-creation": ["view"],
            },
            "user-creations": {
                "staffcreation": ["view"],
            },
            "customers": {
                "customercreations": ["view"],
            },
            "schedule-setup": {
                "staff-templates": ["view", "add", "edit"],
                "alternative-staff-templates": ["view", "add", "edit"],
                "collection-points": ["view"],
                "trip-plans": ["view"],
            },
            "schedule-operations": {
                "daily-trip-assignments": ["view", "edit"],
                "daily-trip-collection-points": ["view"],
                "householdcollection-events": ["view"],
                "secondary-bin-collection-events": ["view"],
                "vehicle-breakdowns": ["view", "edit"],
                "daily-trip-logs": ["view"],
            },
        }

    return {}


def apply_role_default_permissions(permissions, role_name):
    return merge_permission_maps(permissions or {}, role_default_permissions(role_name))


def normalize_permission_key(value):
    text = (value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def normalize_action_key(value):
    normalized = re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())
    if normalized in {"permadd", "create"}:
        return "add"
    if normalized in {"display", "visible", "list", "read", "show"}:
        return "view"
    if normalized in {"update", "change"}:
        return "edit"
    if normalized in {"remove"}:
        return "delete"
    return normalized


def permission_action_name(action):
    """Return variable_name if available, else action_name."""
    if not action:
        return None
    return action.variable_name or action.action_name


def _safe_get(obj, attr, default=None):
    """Safely get attribute from object, returning default if obj is None."""
    if obj is None:
        return default
    return getattr(obj, attr, default)


def build_action_permissions(queryset):
    permissions = {}
    for perm in queryset.order_by("order_no"):
        main_name = _safe_get(perm.mainscreen, "mainscreen_name", "")
        screen_name = _safe_get(perm.userscreen, "userscreen_name", "")
        action_name = permission_action_name(perm.userscreenaction)

        screen_map = permissions.setdefault(main_name, {})
        actions = screen_map.setdefault(screen_name, [])
        if action_name and action_name not in actions:
            actions.append(action_name)

    return permissions


def build_permission_details(action_queryset, column_queryset=None):
    details = {}
    screen_meta = {}

    for perm in action_queryset.order_by("mainscreen_id", "userscreen_id", "order_no"):
        main_name = _safe_get(perm.mainscreen, "mainscreen_name", "")
        screen_name = _safe_get(perm.userscreen, "userscreen_name", "")
        action_name = permission_action_name(perm.userscreenaction)

        screen_payload = details.setdefault(main_name, {}).setdefault(
            screen_name,
            {
                "mainScreenId": perm.mainscreen_id,
                "mainScreenName": main_name,
                "mainScreenKey": normalize_permission_key(main_name),
                "userScreenId": perm.userscreen_id,
                "screenKey": normalize_permission_key(
                    _safe_get(perm.userscreen, "folder_name", "") or screen_name
                ),
                "folderName": _safe_get(perm.userscreen, "folder_name", None),
                "orderNo": _safe_get(perm.userscreen, "order_no", None),
                "permissions": base_action_map()
            },
        )
        screen_meta[perm.userscreen_id] = (main_name, screen_name)
        if action_name:
            screen_payload["permissions"][action_name] = True

    if column_queryset is None:
        column_queryset = UserScreenColumnPermission.objects.none()

    for column_permission in column_queryset.order_by("userscreen_id", "order_no"):
        screen_id = column_permission.userscreen_id
        if screen_id not in screen_meta:
            main_name = _safe_get(column_permission.userscreen.mainscreen, "mainscreen_name", "")
            screen_name = _safe_get(column_permission.userscreen, "userscreen_name", "")
            screen_meta[screen_id] = (main_name, screen_name)
            details.setdefault(main_name, {}).setdefault(
                screen_name,
                {
                    "mainScreenId": column_permission.userscreen.mainscreen_id if column_permission.userscreen else "",
                    "mainScreenName": main_name,
                    "mainScreenKey": normalize_permission_key(main_name),
                    "userScreenId": screen_id,
                    "screenKey": normalize_permission_key(
                        _safe_get(column_permission.userscreen, "folder_name", "") or screen_name
                    ),
                    "folderName": _safe_get(column_permission.userscreen, "folder_name", None),
                    "orderNo": _safe_get(column_permission.userscreen, "order_no", None),
                    "permissions": base_action_map()
                },
            )

        main_name, screen_name = screen_meta[screen_id]
        column = column_permission.column
        details[main_name][screen_name].setdefault("columns", []).append({
            "id": column.unique_id if column else "",
            "columnId": column.unique_id if column else "",
            "fieldName": _safe_get(column, "field_name", ""),
            "displayName": _safe_get(column, "display_name", ""),
            "dataType": _safe_get(column, "data_type", ""),
            "dbColumn": _safe_get(column, "db_column", ""),
            "canView": column_permission.can_view,
            "isRequired": _safe_get(column, "is_required", False),
            "orderNo": column_permission.order_no,
        })

    return details


def build_column_permissions(column_queryset):
    grouped = {}
    flat = []

    for column_permission in column_queryset.order_by(
        "userscreen_id",
        "order_no",
    ):
        userscreen = column_permission.userscreen
        mainscreen = userscreen.mainscreen if userscreen else None
        column = column_permission.column

        payload = {
            "uniqueId": column_permission.unique_id,
            "userTypeId": column_permission.usertype_id,
            "staffUserTypeId": column_permission.staffusertype_id,
            "mainScreenId": mainscreen.unique_id if mainscreen else "",
            "mainScreenName": _safe_get(mainscreen, "mainscreen_name", ""),
            "mainScreenKey": normalize_permission_key(_safe_get(mainscreen, "mainscreen_name", "")),
            "userScreenId": userscreen.unique_id if userscreen else "",
            "userScreenName": _safe_get(userscreen, "userscreen_name", ""),
            "screenKey": normalize_permission_key(
                _safe_get(userscreen, "folder_name", "") or _safe_get(userscreen, "userscreen_name", "")
            ),
            "folderName": _safe_get(userscreen, "folder_name", None),
            "columnId": column.unique_id if column else "",
            "fieldName": _safe_get(column, "field_name", ""),
            "displayName": _safe_get(column, "display_name", ""),
            "dataType": _safe_get(column, "data_type", ""),
            "dbColumn": _safe_get(column, "db_column", ""),
            "canView": column_permission.can_view,
            "isRequired": _safe_get(column, "is_required", False),
            "orderNo": column_permission.order_no,
        }

        flat.append(payload)
        if mainscreen and userscreen:
            grouped.setdefault(mainscreen.mainscreen_name, {}).setdefault(
                userscreen.userscreen_name,
                [],
            ).append(payload)

    return {
        "grouped": grouped,
        "flat": flat,
    }


def build_dashboard_permissions(queryset):
    permissions = {}
    for permission in queryset.order_by("order_no"):
        permissions[permission.widget_name] = permission.is_enabled
    return permissions


def build_module_access(action_queryset, column_queryset=None):
    modules = {}
    screen_lookup = {}

    for perm in action_queryset.order_by(
        "mainscreen_id",
        "userscreen_id",
        "order_no",
    ):
        mainscreen = perm.mainscreen
        userscreen = perm.userscreen
        action_name = permission_action_name(perm.userscreenaction)

        module_entry = modules.setdefault(
            mainscreen.unique_id if mainscreen else "",
            {
                "moduleId": mainscreen.unique_id if mainscreen else "",
                "moduleName": _safe_get(mainscreen, "mainscreen_name", ""),
                "moduleKey": normalize_permission_key(_safe_get(mainscreen, "mainscreen_name", "")),
                "orderNo": _safe_get(mainscreen, "order_no", 0),
                "screens": {},
            },
        )

        screen_entry = module_entry["screens"].setdefault(
            userscreen.unique_id if userscreen else "",
            {
                "userScreenId": userscreen.unique_id if userscreen else "",
                "screenName": _safe_get(userscreen, "userscreen_name", ""),
                "screenKey": normalize_permission_key(
                    _safe_get(userscreen, "folder_name", "") or _safe_get(userscreen, "userscreen_name", "")
                ),
                "folderName": _safe_get(userscreen, "folder_name", None),
                "orderNo": _safe_get(userscreen, "order_no", 0),
                "permissions": base_action_map()
            },
        )
        if userscreen:
            screen_lookup[userscreen.unique_id] = screen_entry

        if action_name:
            screen_entry["permissions"][action_name] = True

    if column_queryset is None:
        column_queryset = UserScreenColumnPermission.objects.none()

    # Modules/screens are re-sorted by order_no below, so only the column
    # order within a screen matters here.
    for column_permission in column_queryset.order_by("order_no"):
        userscreen = column_permission.userscreen
        mainscreen = userscreen.mainscreen if userscreen else None
        column = column_permission.column
        if not userscreen or not mainscreen or not column:
            continue
        module_entry = modules.setdefault(
            mainscreen.unique_id,
            {
                "moduleId": mainscreen.unique_id,
                "moduleName": mainscreen.mainscreen_name,
                "moduleKey": normalize_permission_key(mainscreen.mainscreen_name),
                "orderNo": mainscreen.order_no,
                "screens": {},
            },
        )
        screen_entry = module_entry["screens"].setdefault(
            userscreen.unique_id,
            {
                "userScreenId": userscreen.unique_id,
                "screenName": userscreen.userscreen_name,
                "screenKey": normalize_permission_key(
                    userscreen.folder_name or userscreen.userscreen_name
                ),
                "folderName": userscreen.folder_name,
                "orderNo": userscreen.order_no,
                "permissions": base_action_map(),
            },
        )
        screen_lookup[userscreen.unique_id] = screen_entry

        screen_entry.setdefault("columns", []).append(
            {
                "columnId": column.unique_id,
                "fieldName": column.field_name,
                "displayName": column.display_name,
                "dbColumn": column.db_column,
                "dataType": column.data_type,
                "canView": column_permission.can_view,
                "isRequired": column.is_required,
                "orderNo": column_permission.order_no,
            }
        )

    payload = []
    for module in sorted(modules.values(), key=lambda item: item["orderNo"] or 0):
        screens = sorted(
            module["screens"].values(),
            key=lambda item: item["orderNo"] or 0,
        )
        payload.append(
            {
                "moduleId": module["moduleId"],
                "moduleName": module["moduleName"],
                "moduleKey": module["moduleKey"],
                "orderNo": module["orderNo"],
                "screens": screens,
            }
        )
    return payload


def build_fallback_module_access(permissions):
    module_access = []

    for module_name, screens in sorted((permissions or {}).items()):
        module_entry = {
            "moduleId": None,
            "moduleName": module_name,
            "moduleKey": normalize_permission_key(module_name),
            "orderNo": None,
            "screens": [],
        }

        for screen_name, action_names in sorted((screens or {}).items()):
            action_map = base_action_map()
            for action_name in action_names or []:
                normalized = normalize_permission_key(action_name)
                if normalized:
                    action_map[normalized] = True
            module_entry["screens"].append(
                {
                    "userScreenId": None,
                    "screenName": screen_name,
                    "screenKey": normalize_permission_key(screen_name),
                    "folderName": None,
                    "orderNo": None,
                    "permissions": action_map,
                }
            )

        module_access.append(module_entry)

    return module_access


def infer_app_surfaces(module_access, permissions, role_name=None, user_type=None):
    role_key = normalize_permission_key(role_name)
    user_type_key = normalize_permission_key(user_type)
    module_keys = {module.get("moduleKey") for module in module_access}
    screen_keys = {
        screen.get("screenKey")
        for module in module_access
        for screen in module.get("screens", [])
    }

    surface_keys = []
    if user_type_key in {"customer", "citizen"} or role_key in {"customer", "citizen"}:
        surface_keys.append("citizen")
    elif "driver" in role_key:
        surface_keys.append("driver")
    elif "operator" in role_key:
        surface_keys.append("operator")
    elif "supervisor" in role_key:
        surface_keys.append("supervisor")
    elif any(token in role_key for token in ("admin", "superadmin", "platform")):
        surface_keys.append("admin")
    elif module_keys & {
        "screen-managements",
        "role-assigns",
        "user-creations",
        "transport-masters",
        "audits",
        "masters",
        "common-masters",
        "complaint-ticket",
    }:
        surface_keys.append("admin")
    elif screen_keys & {
        "customercreations",
        
        "trip_plan",
        "attendance-list",
        "alternative-stafftemplate",
    } or module_keys & {"customers", "process", "process-items"}:
        surface_keys.append("operator")

    if not surface_keys and permissions:
        surface_keys.append("admin")

    surfaces = []
    for index, key in enumerate(surface_keys):
        config = APP_SURFACE_CONFIG.get(key)
        if not config:
            continue
        surfaces.append(
            {
                "key": key,
                "label": config["label"],
                "route": config["route"],
                "isDefault": index == 0,
            }
        )
    return surfaces


def build_landing(app_surfaces, module_access):
    if not app_surfaces:
        return None

    first_module = next(
        (module for module in module_access if module.get("screens")),
        None,
    )
    first_screen = None
    if first_module:
        first_screen = next(
            (screen for screen in first_module.get("screens", []) if screen.get("permissions")),
            None,
        )

    primary_surface = app_surfaces[0]
    return {
        "surfaceKey": primary_surface["key"],
        "route": primary_surface["route"],
        "moduleKey": first_module.get("moduleKey") if first_module else None,
        "screenKey": first_screen.get("screenKey") if first_screen else None,
    }


def build_permission_version(permissions, column_permissions):
    raw_payload = json.dumps(
        {
            "permissions": permissions or {},
            "columns": (column_permissions or {}).get("flat", []),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()[:16]


# ============================================================
# MOBILE APP LAYER
# ============================================================
# Ported from the private backend. Everything above resolves permissions from
# role + geography exactly as before; this section only layers a staff
# member's own access configuration on top and reports the mobile app modules
# and screens alongside the same payload.


def staff_access_config(staff_unique_id):
    """The staff member's active access configuration, or None."""
    if not staff_unique_id:
        return None

    from app.models.superadmin.staff_management.staff_access_configuration import (
        StaffAccessConfiguration,
    )

    return (
        StaffAccessConfiguration.objects
        .filter(staff_id=staff_unique_id, is_active=True, is_deleted=False)
        .first()
    )


def staff_configured_permissions(config):
    """{module: {screen: [actions]}} from a configuration's granted rows."""
    if config is None:
        return {}

    permissions = {}
    from app.models.superadmin.screen_management.mainscreen import MainScreen
    from app.models.superadmin.screen_management.userscreen import UserScreen
    from app.models.superadmin.screen_management.userscreenaction import UserScreenAction

    # Plain id columns: resolve every referenced screen/action in bulk.
    rows = list(config.granted_permissions.filter(is_active=True, is_deleted=False))
    mainscreens = MainScreen.objects.in_bulk({row.mainscreen_id for row in rows})
    userscreens = UserScreen.objects.in_bulk({row.userscreen_id for row in rows})
    actions_by_id = UserScreenAction.objects.in_bulk({row.userscreenaction_id for row in rows})
    for row in rows:
        mainscreen = mainscreens.get(row.mainscreen_id)
        userscreen = userscreens.get(row.userscreen_id)
        action = actions_by_id.get(row.userscreenaction_id)
        if not (mainscreen and userscreen and action):
            continue
        module_name = mainscreen.mainscreen_name
        screen_name = userscreen.userscreen_name
        action_name = (
            action.variable_name
            or action.action_name
            or ""
        ).lower()
        if not action_name:
            continue
        actions = permissions.setdefault(module_name, {}).setdefault(screen_name, [])
        if action_name not in actions:
            actions.append(action_name)
    return permissions


# Parent screen -> child screens with no permission row of their own. Each
# child inherits every action granted on its parent (merged with any grant of
# its own), so the frontend still shows its menu/page. The middleware applies
# the same grouping by resource name (PERMISSION_SCREEN_CHILDREN there).
PERMISSION_SCREEN_CHILDREN = {
    "staff-user-type": ("contractorusertypes", "governmentusertypes"),
    "householdcollection-events": ("wastecollections",),
    "daily-trip-plans": ("daily-trip-assignments", "daily-trip-collection-points"),
}


def expand_child_screen_permissions(permissions):
    """Copy each parent screen's actions onto its child screens."""
    if not permissions:
        return permissions
    expanded = {}
    for module, screens in permissions.items():
        screens = {screen: list(actions) for screen, actions in (screens or {}).items()}
        by_key = {normalize_permission_key(screen): screen for screen in screens}
        for parent, children in PERMISSION_SCREEN_CHILDREN.items():
            parent_screen = by_key.get(normalize_permission_key(parent))
            if not parent_screen:
                continue
            for child in children:
                child_screen = by_key.get(normalize_permission_key(child), child)
                actions = screens.setdefault(child_screen, [])
                for action in screens[parent_screen]:
                    if action not in actions:
                        actions.append(action)
        expanded[module] = screens
    return expanded


def apply_staff_access_configuration(permissions, staff_unique_id):
    """Layer a staff member's own configuration onto their role permissions.

    No configuration means no change at all — every existing login keeps
    resolving exactly as it did. With one, its grants are merged on top; in
    strict mode they replace the role's entirely, which is what makes
    unticking a screen actually remove access.
    """
    config = staff_access_config(staff_unique_id)
    if config is None:
        return expand_child_screen_permissions(permissions)

    configured = staff_configured_permissions(config)
    if getattr(config, "enforce_strict_permissions", False):
        return expand_child_screen_permissions(configured)
    if not configured:
        return expand_child_screen_permissions(permissions)
    return expand_child_screen_permissions(merge_permission_maps(permissions or {}, configured))


def staff_app_modules(config):
    """Surface keys ticked on a StaffAccessConfiguration."""
    if config is None:
        return []
    return list(
        config.app_modules.filter(is_active=True, is_deleted=False)
        .values_list("surface_key", flat=True)
    )


def surfaces_from_app_modules(app_modules):
    """Surfaces for the app modules ticked on an access configuration.

    Deriving the mobile surfaces from grants rather than from a role name is
    what stops an unrelated web permission handing someone an app they have no
    screens for.
    """
    from app.utils.app_feature_grants import APP_SURFACE_KEYS

    return [surface for surface in APP_SURFACE_KEYS if surface in (app_modules or [])]


def build_app_screens(permissions, app_modules, citizen_screens=None):
    """Which mobile screens to render, per granted surface."""
    from app.utils.app_feature_grants import visible_screens

    return {
        surface: visible_screens(
            permissions, surface, citizen_screens=citizen_screens
        )
        for surface in (app_modules or [])
    }


def finalize_permission_payload(
    payload,
    *,
    permissions=None,
    role_name=None,
    user_type=None,
    app_module=None,
    app_modules=None,
):
    effective_permissions = permissions if permissions is not None else payload.get("permissions", {})
    if permissions is not None and effective_permissions != payload.get("permissions", {}):
        module_access = build_fallback_module_access(effective_permissions)
    else:
        module_access = payload.get("module_access") or build_fallback_module_access(
            effective_permissions
        )

    effective_modules = (
        app_modules if app_modules is not None else payload.get("app_modules")
    )

    # App modules ticked on an access configuration are the authoritative
    # answer for the mobile app. Only when none are ticked does this fall back
    # to the original role/module inference, so every existing web login keeps
    # the surfaces it had.
    granted_surfaces = surfaces_from_app_modules(effective_modules)
    if granted_surfaces:
        preferred = normalize_permission_key(app_module)
        if preferred in granted_surfaces:
            granted_surfaces.remove(preferred)
            granted_surfaces.insert(0, preferred)
        app_surfaces = [
            {
                "key": key,
                "label": APP_SURFACE_CONFIG[key]["label"],
                "route": APP_SURFACE_CONFIG[key]["route"],
                "isDefault": index == 0,
            }
            for index, key in enumerate(granted_surfaces)
            if key in APP_SURFACE_CONFIG
        ]
    else:
        app_surfaces = infer_app_surfaces(
            module_access,
            effective_permissions,
            role_name=role_name,
            user_type=user_type,
        )

    return {
        **payload,
        "permissions": effective_permissions,
        "module_access": module_access,
        "app_surfaces": app_surfaces,
        "landing": build_landing(app_surfaces, module_access),
        "permission_version": build_permission_version(
            effective_permissions,
            payload.get("column_permissions", {}),
        ),
        "generated_at": timezone.now().isoformat(),
    }


def permission_querysets(
    *,
    usertype_unique_id=None,
    staffusertype_unique_id=None,
    contractorusertype_unique_id=None,
    governmentusertype_unique_id=None,
    state_unique_id=None,
    district_unique_id=None,
    area_type_unique_id=None,
    local_body_type=None,
    local_body_id=None,
    permission_owner_kind=None,
    staff_id=None,
    include_all=False,
    **_unused,
):
    action_queryset = UserScreenPermission.objects.filter(
        is_active=True,
        is_deleted=False,
    )
    column_queryset = UserScreenColumnPermission.objects.filter(
        is_active=True,
        is_deleted=False,
    )
    dashboard_queryset = DashboardWidgetPermission.objects.filter(
        is_active=True,
        is_deleted=False,
    )

    if include_all:
        return action_queryset, column_queryset, dashboard_queryset

    if local_body_type and local_body_id:
        filters = {
            "local_body_type": local_body_type,
            "local_body_id": local_body_id,
        }
        if state_unique_id:
            filters["state_id"] = state_unique_id
        if district_unique_id:
            filters["district_id"] = district_unique_id
        if area_type_unique_id:
            filters["area_type_id"] = area_type_unique_id
        if permission_owner_kind:
            filters["permission_owner_kind"] = permission_owner_kind
        if staff_id:
            filters["staff_id"] = staff_id

        return (
            action_queryset.filter(**filters),
            column_queryset.filter(**filters),
            dashboard_queryset.filter(**filters),
        )

    if permission_owner_kind or staff_id or state_unique_id or district_unique_id or area_type_unique_id:
        filters = {
            "local_body_type__isnull": True,
            "local_body_id__isnull": True,
        }
        if state_unique_id:
            filters["state_id"] = state_unique_id
        if district_unique_id:
            filters["district_id"] = district_unique_id
        if area_type_unique_id:
            filters["area_type_id"] = area_type_unique_id
        if permission_owner_kind:
            filters["permission_owner_kind"] = permission_owner_kind
        if staff_id:
            filters["staff_id"] = staff_id

        return (
            action_queryset.filter(**filters),
            column_queryset.filter(**filters),
            dashboard_queryset.filter(**filters),
        )

    if not usertype_unique_id:
        return action_queryset.none(), column_queryset.none(), dashboard_queryset.none()

    filters = {
        "usertype_id": usertype_unique_id,
    }
    if staffusertype_unique_id:
        filters["staffusertype_id"] = staffusertype_unique_id
    elif contractorusertype_unique_id:
        filters["contractorusertype_id"] = contractorusertype_unique_id
    elif governmentusertype_unique_id:
        filters["governmentusertype_id"] = governmentusertype_unique_id
    else:
        filters["staffusertype_id__isnull"] = True
        filters["contractorusertype_id__isnull"] = True
        filters["governmentusertype_id__isnull"] = True

    return (
        action_queryset.filter(**filters),
        column_queryset.filter(**filters),
        dashboard_queryset.filter(**filters),
    )


def resolve_permission_payload(**filters):
    action_queryset, column_queryset, dashboard_queryset = permission_querysets(**filters)
    permissions = build_action_permissions(action_queryset)
    permissions = apply_role_default_permissions(
        permissions,
        filters.get("role_name"),
    )

    # The staff member's own access configuration, layered on top of the role
    # resolution above (or replacing it in strict mode). No configuration means
    # no change, so nothing that worked before this port behaves differently.
    staff_unique_id = filters.get("staff_id") or filters.get("staff_unique_id")
    config = staff_access_config(staff_unique_id)
    permissions = apply_staff_access_configuration(permissions, staff_unique_id)

    # Which apps this person may open, and which screens to render in each.
    app_modules = filters.get("app_modules")
    if app_modules is None:
        app_modules = staff_app_modules(config)
    app_screens = build_app_screens(
        permissions, app_modules, citizen_screens=filters.get("citizen_screens")
    )

    payload = {
        "permissions": permissions,
        "permission_details": build_permission_details(action_queryset, column_queryset),
        "column_permissions": build_column_permissions(column_queryset),
        "module_access": build_fallback_module_access(permissions),
        "dashboard_permissions": build_dashboard_permissions(dashboard_queryset),
        "app_modules": app_modules,
        "app_screens": app_screens,
        "strict_permissions": bool(
            getattr(config, "enforce_strict_permissions", False)
        ),
    }
    return finalize_permission_payload(
        payload,
        role_name=filters.get("role_name"),
        user_type=filters.get("user_type"),
        app_module=filters.get("app_module"),
        app_modules=app_modules,
    )


def _intersect_action_permissions(super_admin_permissions, staff_permissions):
    """
    Final Permission = Super Admin Screen Permission ∩ Staff Screen
    Permission. Keeps only modules/screens/actions granted by BOTH sides.
    """
    intersected = {}
    for module_name, screens in (super_admin_permissions or {}).items():
        staff_screens = (staff_permissions or {}).get(module_name)
        if not staff_screens:
            continue
        for screen_name, actions in screens.items():
            staff_actions = staff_screens.get(screen_name)
            if not staff_actions:
                continue
            common_actions = [action for action in actions if action in staff_actions]
            if common_actions:
                intersected.setdefault(module_name, {})[screen_name] = common_actions
    return intersected


def _intersect_dashboard_permissions(super_admin_widgets, staff_widgets):
    intersected = {}
    for widget_name, super_admin_enabled in (super_admin_widgets or {}).items():
        staff_enabled = (staff_widgets or {}).get(widget_name, False)
        intersected[widget_name] = bool(super_admin_enabled) and bool(staff_enabled)
    return intersected


def resolve_intersected_permission_payload(
    *,
    state_unique_id=None,
    district_unique_id=None,
    area_type_unique_id=None,
    local_body_type=None,
    local_body_id=None,
    staff_id=None,
    role_name=None,
    user_type=None,
):
    """
    Login-time resolution for a Local-Body-scoped staff member: Screen
    Permission is the intersection of the Super Admin baseline (configured
    directly on the Local Body) and this specific staff member's own grants
    (configured via Staff Access Configuration) — both are independent row
    sets in the same tables, distinguished by `permission_owner_kind` +
    `staff_id`. Field Permission and Dashboard Widgets come from the Super
    Admin baseline only; Field Permission has no staff-side counterpart to
    intersect against, and Dashboard Widgets are intersected the same way
    Screen Permission is (a widget must be enabled by both to show).
    """
    scope = {
        "state_unique_id": state_unique_id,
        "district_unique_id": district_unique_id,
        "area_type_unique_id": area_type_unique_id,
        "local_body_type": local_body_type,
        "local_body_id": local_body_id,
    }

    super_admin_action_qs, super_admin_column_qs, super_admin_dashboard_qs = permission_querysets(
        **scope, permission_owner_kind="super_admin",
    )
    staff_action_qs, _staff_column_qs, staff_dashboard_qs = permission_querysets(
        **scope, permission_owner_kind="staff", staff_id=staff_id,
    )

    super_admin_permissions = build_action_permissions(super_admin_action_qs)
    staff_permissions = build_action_permissions(staff_action_qs)
    final_permissions = _intersect_action_permissions(super_admin_permissions, staff_permissions)
    final_permissions = apply_role_default_permissions(final_permissions, role_name)

    super_admin_dashboard = build_dashboard_permissions(super_admin_dashboard_qs)
    staff_dashboard = build_dashboard_permissions(staff_dashboard_qs)
    final_dashboard = _intersect_dashboard_permissions(super_admin_dashboard, staff_dashboard)

    # permission_details/column_permissions must reflect exactly the
    # (screen, action) pairs that survived the intersection — the Super
    # Admin baseline alone may grant more screens/actions than this specific
    # staff member was actually given.
    granted_action_ids = set()
    granted_userscreen_ids = set()
    for perm in super_admin_action_qs:
        screen_actions = final_permissions.get(_safe_get(perm.mainscreen, "mainscreen_name", ""), {}).get(
            _safe_get(perm.userscreen, "userscreen_name", "")
        )
        action_name = permission_action_name(perm.userscreenaction)
        if screen_actions and action_name in screen_actions:
            granted_action_ids.add(perm.unique_id)
            granted_userscreen_ids.add(perm.userscreen_id)

    filtered_action_qs = super_admin_action_qs.filter(unique_id__in=granted_action_ids)
    filtered_column_qs = super_admin_column_qs.filter(userscreen_id__in=granted_userscreen_ids)

    payload = {
        "permissions": final_permissions,
        "permission_details": build_permission_details(filtered_action_qs, filtered_column_qs),
        "column_permissions": build_column_permissions(filtered_column_qs),
        "module_access": build_fallback_module_access(final_permissions),
        "dashboard_permissions": final_dashboard,
        "super_admin_permissions": super_admin_permissions,
        "staff_permissions": staff_permissions,
    }
    return finalize_permission_payload(payload, role_name=role_name, user_type=user_type)
