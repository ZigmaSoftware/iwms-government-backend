from app.middleware.module_permission_middleware import (
    MODULE_RESOURCE_ALLOWLIST,
    ModulePermissionMiddleware,
    _resource_allowlist_candidates,
)


def _resource_is_allowed(module, permission_resource, route_resource):
    allowed_resource_keys = {
        ModulePermissionMiddleware._normalize_permission_key(resource)
        for resource in MODULE_RESOURCE_ALLOWLIST[module]
    }
    resource_candidates = _resource_allowlist_candidates(
        permission_resource,
        route_resource,
    )
    return any(
        ModulePermissionMiddleware._normalize_permission_key(candidate)
        in allowed_resource_keys
        for candidate in resource_candidates
    )


def test_department_master_permission_matches_departments_route():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "department-masters": ["add", "delete", "edit", "show", "view"],
    }

    assert _resource_is_allowed("masters", "Department", "departments")
    assert middleware._resolve_allowed_actions(
        permissions,
        "Department",
        "departments",
    ) == ["add", "delete", "edit", "show", "view"]


def test_designation_master_permission_matches_designations_route():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "designation-masters": ["add", "delete", "edit", "show", "view"],
    }

    assert _resource_is_allowed("masters", "Designation", "designations")
    assert middleware._resolve_allowed_actions(
        permissions,
        "Designation",
        "designations",
    ) == ["add", "delete", "edit", "show", "view"]


def test_contractor_usertype_permission_matches_contractorusertypes_route():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "contractorusertypes": ["view", "add", "edit", "delete"],
    }

    assert _resource_is_allowed("role-assigns", "ContractorUserType", "contractorusertypes")
    assert middleware._resolve_allowed_actions(
        permissions,
        "ContractorUserType",
        "contractorusertypes",
    ) == ["view", "add", "edit", "delete"]


def test_staff_template_creation_permission_matches_staff_templates_route():
    middleware = ModulePermissionMiddleware(lambda request: None)
    permissions = {
        "staff-templates": ["view", "add", "edit", "delete"],
    }

    assert _resource_is_allowed(
        "schedule-masters",
        "StaffTemplateCreation",
        "staff-templates",
    )
    assert middleware._resolve_allowed_actions(
        permissions,
        "StaffTemplateCreation",
        "staff-templates",
    ) == ["view", "add", "edit", "delete"]
