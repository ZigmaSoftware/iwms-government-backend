import hashlib
import json
import re

from django.utils import timezone

from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.screen_managements.companyuserscreenpermission import UserScreenPermission
from app.models.screen_managements.dashboardwidgetpermission import DashboardWidgetPermission


ACTION_KEYS = ("show", "view", "add", "edit", "delete", "approve", "export")

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


def normalize_permission_key(value):
    text = (value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def build_action_permissions(queryset):
    permissions = {}
    for perm in queryset.order_by("order_no"):
        main_name = perm.mainscreen_id.mainscreen_name
        screen_name = perm.userscreen_id.userscreen_name
        action_name = (
            perm.userscreenaction_id.variable_name
            or perm.userscreenaction_id.action_name
            or ""
        ).lower()

        screen_map = permissions.setdefault(main_name, {})
        actions = screen_map.setdefault(screen_name, [])
        if action_name and action_name not in actions:
            actions.append(action_name)

    return permissions


def build_permission_details(action_queryset, column_queryset=None):
    details = {}
    screen_meta = {}

    for perm in action_queryset.order_by("mainscreen_id__order_no", "userscreen_id__order_no", "order_no"):
        main_name = perm.mainscreen_id.mainscreen_name
        screen_name = perm.userscreen_id.userscreen_name
        action_name = (
            perm.userscreenaction_id.variable_name
            or perm.userscreenaction_id.action_name
            or ""
        ).lower()

        screen_payload = details.setdefault(main_name, {}).setdefault(
            screen_name,
            {
                "mainScreenId": perm.mainscreen_id_id,
                "mainScreenName": main_name,
                "mainScreenKey": normalize_permission_key(main_name),
                "userScreenId": perm.userscreen_id_id,
                "screenKey": normalize_permission_key(
                    getattr(perm.userscreen_id, "folder_name", "") or screen_name
                ),
                "folderName": getattr(perm.userscreen_id, "folder_name", None),
                "orderNo": getattr(perm.userscreen_id, "order_no", None),
                "permissions": base_action_map(),
                "columns": [],
            },
        )
        screen_meta[perm.userscreen_id_id] = (main_name, screen_name)
        if action_name:
            screen_payload["permissions"][action_name] = True

    if column_queryset is None:
        column_queryset = CompanyUserScreenColumnPermission.objects.none()

    for column_permission in column_queryset.order_by("userscreen_id__order_no", "order_no"):
        screen_id = column_permission.userscreen_id_id
        if screen_id not in screen_meta:
            main_name = column_permission.userscreen_id.mainscreen_id.mainscreen_name
            screen_name = column_permission.userscreen_id.userscreen_name
            screen_meta[screen_id] = (main_name, screen_name)
            details.setdefault(main_name, {}).setdefault(
                screen_name,
                {
                    "mainScreenId": column_permission.userscreen_id.mainscreen_id_id,
                    "mainScreenName": main_name,
                    "mainScreenKey": normalize_permission_key(main_name),
                    "userScreenId": screen_id,
                    "screenKey": normalize_permission_key(
                        getattr(column_permission.userscreen_id, "folder_name", "")
                        or screen_name
                    ),
                    "folderName": getattr(column_permission.userscreen_id, "folder_name", None),
                    "orderNo": getattr(column_permission.userscreen_id, "order_no", None),
                    "permissions": base_action_map(),
                    "columns": [],
                },
            )

        main_name, screen_name = screen_meta[screen_id]
        column = column_permission.column_id
        details[main_name][screen_name]["columns"].append({
            "id": column.unique_id,
            "columnId": column.unique_id,
            "fieldName": column.field_name,
            "displayName": column.display_name,
            "dataType": column.data_type,
            "dbColumn": column.db_column,
            "canView": column_permission.can_view,
            "isRequired": column.is_required,
            "orderNo": column_permission.order_no,
        })

    return details


def build_column_permissions(column_queryset):
    grouped = {}
    flat = []

    for column_permission in column_queryset.order_by(
        "userscreen_id__mainscreen_id__order_no",
        "userscreen_id__order_no",
        "order_no",
    ):
        userscreen = column_permission.userscreen_id
        mainscreen = userscreen.mainscreen_id
        column = column_permission.column_id

        payload = {
            "uniqueId": column_permission.unique_id,
            "userTypeId": column_permission.usertype_id_id,
            "staffUserTypeId": column_permission.staffusertype_id_id,
            "mainScreenId": mainscreen.unique_id,
            "mainScreenName": mainscreen.mainscreen_name,
            "mainScreenKey": normalize_permission_key(mainscreen.mainscreen_name),
            "userScreenId": userscreen.unique_id,
            "userScreenName": userscreen.userscreen_name,
            "screenKey": normalize_permission_key(userscreen.folder_name or userscreen.userscreen_name),
            "folderName": userscreen.folder_name,
            "columnId": column.unique_id,
            "fieldName": column.field_name,
            "displayName": column.display_name,
            "dataType": column.data_type,
            "dbColumn": column.db_column,
            "canView": column_permission.can_view,
            "isRequired": column.is_required,
            "orderNo": column_permission.order_no,
        }

        flat.append(payload)
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
        "mainscreen_id__order_no",
        "userscreen_id__order_no",
        "order_no",
    ):
        mainscreen = perm.mainscreen_id
        userscreen = perm.userscreen_id
        action_name = (
            perm.userscreenaction_id.variable_name
            or perm.userscreenaction_id.action_name
            or ""
        ).lower()

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
                "columns": [],
            },
        )
        screen_lookup[userscreen.unique_id] = screen_entry

        if action_name:
            screen_entry["permissions"][action_name] = True

    if column_queryset is None:
        column_queryset = CompanyUserScreenColumnPermission.objects.none()

    for column_permission in column_queryset.order_by(
        "userscreen_id__mainscreen_id__order_no",
        "userscreen_id__order_no",
        "order_no",
    ):
        userscreen = column_permission.userscreen_id
        mainscreen = userscreen.mainscreen_id
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
                "columns": [],
            },
        )
        screen_lookup[userscreen.unique_id] = screen_entry

        column = column_permission.column_id
        screen_entry["columns"].append(
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
                    "columns": [],
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


def finalize_permission_payload(payload, *, permissions=None, role_name=None, user_type=None):
    effective_permissions = permissions if permissions is not None else payload.get("permissions", {})
    if permissions is not None and effective_permissions != payload.get("permissions", {}):
        module_access = build_fallback_module_access(effective_permissions)
    else:
        module_access = payload.get("module_access") or build_fallback_module_access(
            effective_permissions
        )

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
    include_all=False,
    **_unused,
):
    action_queryset = UserScreenPermission.objects.filter(
        is_active=True,
        is_deleted=False,
    ).select_related(
        "mainscreen_id",
        "userscreen_id",
        "userscreenaction_id",
        "staffusertype_id",
        "contractorusertype_id",
        "governmentusertype_id",
    )
    column_queryset = CompanyUserScreenColumnPermission.objects.filter(
        is_active=True,
        is_deleted=False,
    ).select_related(
        "userscreen_id",
        "userscreen_id__mainscreen_id",
        "column_id",
        "staffusertype_id",
        "contractorusertype_id",
        "governmentusertype_id",
    )
    dashboard_queryset = DashboardWidgetPermission.objects.filter(
        is_active=True,
        is_deleted=False,
    ).select_related(
        "staffusertype_id",
        "contractorusertype_id",
        "governmentusertype_id",
    )

    if include_all:
        return action_queryset, column_queryset, dashboard_queryset

    if not usertype_unique_id:
        return action_queryset.none(), column_queryset.none(), dashboard_queryset.none()

    filters = {
        "usertype_id_id": usertype_unique_id,
    }
    if staffusertype_unique_id:
        filters["staffusertype_id_id"] = staffusertype_unique_id
    elif contractorusertype_unique_id:
        filters["contractorusertype_id_id"] = contractorusertype_unique_id
    elif governmentusertype_unique_id:
        filters["governmentusertype_id_id"] = governmentusertype_unique_id
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
    payload = {
        "permissions": build_action_permissions(action_queryset),
        "permission_details": build_permission_details(action_queryset, column_queryset),
        "column_permissions": build_column_permissions(column_queryset),
        "module_access": build_module_access(action_queryset, column_queryset),
        "dashboard_permissions": build_dashboard_permissions(dashboard_queryset),
    }
    return finalize_permission_payload(
        payload,
        role_name=filters.get("role_name"),
        user_type=filters.get("user_type"),
    )
