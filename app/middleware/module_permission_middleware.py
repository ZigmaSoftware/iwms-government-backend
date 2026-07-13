import jwt
import re

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from app.models.user_creations.staffcreation import Staffcreation
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.district_leader_login import DistrictLeaderLogin
from app.utils.hierarchy import local_body_scope_for_staff
from app.utils.permission_response import (
    resolve_intersected_permission_payload,
    resolve_permission_payload,
)


# ============================================================
# HTTP → ACTION MAP
# ============================================================

HTTP_ACTION_MAP = {
    "POST": "add",
    "GET": "view",
    "HEAD": "view",
    "PUT": "edit",
    "PATCH": "edit",
    "DELETE": "delete",
}


# ============================================================
# API PATH CONFIG
# ============================================================

API_AUTH_PREFIXES = (
    "/api/mobile/",
    "/api/desktop/",
    "/api/v1/",
)

AUTH_ONLY_SUFFIXES = (
    "register/",
    "recognize/",
    "employee/",
    "staff-profile/",
    "waste/",
    "attendance-list/",
    "localbody/",        # panchayat leader portal — auth only, no module permission check
    "districtbody/",     # district leader portal — auth only, no module permission check
)

AUTH_ONLY_PREFIXES = tuple(
    prefix + suffix
    for prefix in API_AUTH_PREFIXES
    for suffix in AUTH_ONLY_SUFFIXES
)

PLATFORM_PREFIXES = (
    "/api/platform/",
)

PUBLIC_PREFIXES = (
    "/media/",
    "/api/v1/publicgrivence/",
)

COMMON_AUDIT_CREATE_PATHS = tuple(
    prefix + "audits/common-audit/"
    for prefix in API_AUTH_PREFIXES
)


# ============================================================
# MODULE → RESOURCE ALLOWLIST
# (THIS MUST MATCH ViewSet.permission_resource)
# ============================================================

MODULE_RESOURCE_ALLOWLIST = {
    "common-masters": {
        "Continent",
        "Country",
        "State",
    },
    "masters": {
        "District",
        "Panchayat",
        "AreaType",
        "Corporation",
        "Municipality",
        "TownPanchayat",
        "PanchayatUnion",
        "AdministrativeHierarchy",
        "Department",
        "Designation",
    },
    "waste-types": {
        "Property",
        "SubProperty",
    },
    "assets": {
        "Bin",
        "CollectionPoint",
        "WasteType",
        "Bin"
    },
    "screen-managements": {
        "MainScreenType",
        "MainScreen",
        "UserScreen",
        "UserScreenAction",
        "UserScreenPermission",
        "CompanyUserScreenPermission",
        "userscreenpermissions",
        "companywisescreenpermissions",
        "column-permissions",
        "DashboardWidgetPermission",
    },
    "role-assigns": {
        "UserType",
        "StaffUserType",
        "ContractorUserType",
    },
    "user-creations": {
        "UsersCreation",
        "StaffCreation",
        "StaffAccessConfiguration",
        "StaffTemplateCreation",
        "AlternativeStaffTemplate",
        "UnassignedStaffPool",
    },
    "process-items": set(),
    "customer-masters": {
        "CustomerCreation",
        "WasteCollection",
        "FeedBack",
        "UserChargeRule",
    },
    "complaint-ticket": {
        "ComplaintTicket",
        "ComplaintModule",
        "ComplaintCategory",
        "ComplaintSubcategory",
        "ComplaintPriority",
        "ComplaintStatus",
        "ComplaintSource",
        "ComplaintLanguage",
        "ComplaintTeam",
        "ComplaintSlaRule",
        "ComplaintRoutingRule",
        "ComplaintFeedback",
        "ComplaintReopenHistory",
        "ComplaintAddressChange",
    },
    "transport-masters": {
        "VehicleTypeCreation",
        "VehicleCreation",
        "TripAttendance",
        "Fuel",
    },
    "schedule-masters": {
        "StaffTemplateCreation",
        "AlternativeStaffTemplate",
        "CollectionPoint",
        "TripPlan",
        "TripPlanCollectionPoint",
        "DailyTripAssignment",
        "DailyTripCollectionPoint",
        "BinCollectionEvent",
        "DailyTripLog",
        "DailyWasteComparison",
        "MonthlyWasteComparisonReport",
    },
    "audits": {
        "VehicleTripAudit",
        "TripExceptionLog",
        "StaffTemplateAuditLog",
        "LoginAudit",
        "CommonAudit",
    },
}

PROTECTED_MODULES = tuple(MODULE_RESOURCE_ALLOWLIST.keys())

MODULE_PERMISSION_ALIASES = {
    "customer-masters": "customers",
    "process-items": "process",
}

RESOURCE_PERMISSION_ALIASES = {
    "Bin": ("bins",),
    "Department": ("departments", "department-masters"),
    "Designation": ("designations", "designation-masters"),
    "StaffTemplateCreation": ("StaffTemplate", "staff-templates"),
    "userscreenpermissions": ("UserScreenPermission", "CompanyUserScreenPermission"),
    "companywisescreenpermissions": ("UserScreenPermission", "CompanyUserScreenPermission"),
    "column-permissions": ("UserScreenPermission", "CompanyUserScreenPermission"),
}


# ============================================================
# HELPERS
# ============================================================

def _split_path(path):
    return [p for p in path.split("?")[0].split("/") if p]


def _module_from_path(path):
    parts = _split_path(path)
    for part in parts:
        if part == "api":
            continue
        if part.startswith("v") and part[1:].isdigit():
            continue
        if part in PROTECTED_MODULES:
            return part
    return None


def _route_resource_from_path(path, module):
    parts = _split_path(path)
    try:
        module_index = parts.index(module)
    except ValueError:
        return None

    if module_index + 1 >= len(parts):
        return None

    resource = parts[module_index + 1]
    if resource and not resource.startswith("v"):
        return resource
    return None


def _resource_allowlist_candidates(permission_resource, route_resource=None):
    return {
        candidate
        for candidate in (
            permission_resource,
            route_resource,
            *RESOURCE_PERMISSION_ALIASES.get(permission_resource, ()),
        )
        if candidate
    }


def _authenticate_request(request):
    auth = request.headers.get("Authorization")

    if not auth or not auth.startswith("Bearer "):
        return JsonResponse({"detail": "Authorization token missing"}, status=401)

    token = auth.split(" ", 1)[1]
    token = "".join(token.split())

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return JsonResponse({"detail": "Token expired"}, status=401)
    except jwt.InvalidTokenError:
        return JsonResponse({"detail": "Invalid token"}, status=401)

    unique_id = payload.get("unique_id")
    if not unique_id:
        return JsonResponse({"detail": "Invalid token payload"}, status=401)

    # Staff
    staff = Staffcreation.objects.filter(staff_unique_id=unique_id).first()
    if staff:
        request.user = staff
        request.jwt_payload = payload
        return None

    # Customer
    customer = CustomerCreation.objects.filter(unique_id=unique_id).first()
    if customer:
        request.user = customer
        request.jwt_payload = payload
        return None

    # Panchayat leader (localbody portal)
    leader = PanchayatLeaderLogin.objects.select_related(
        "panchayat_id"
    ).filter(unique_id=unique_id).first()
    if leader:
        request.user = leader
        request.jwt_payload = payload
        return None

    # District leader (districtbody portal)
    district_leader = DistrictLeaderLogin.objects.select_related(
        "district_id"
    ).filter(unique_id=unique_id).first()
    if district_leader:
        request.user = district_leader
        request.jwt_payload = payload
        return None

    # Platform user
    UserModel = get_user_model()
    user = UserModel.objects.filter(unique_id=unique_id).first()
    if not user:
        user_id = payload.get("user_id")
        if user_id:
            user = UserModel.objects.filter(pk=user_id).first()

    if user:
        request.user = user
        request.jwt_payload = payload
        return None

    return JsonResponse({"detail": "User not found"}, status=401)


def _permission_filters_for_user(user):
    usertype = getattr(user, "user_type_id", None)
    staffusertype = getattr(user, "staffusertype_id", None)
    contractorusertype = getattr(user, "contractorusertype_id", None)
    governmentusertype = getattr(user, "governmentusertype_id", None)

    usertype_unique_id = getattr(usertype, "unique_id", None)
    staffusertype_unique_id = getattr(staffusertype, "unique_id", None)
    contractorusertype_unique_id = getattr(contractorusertype, "unique_id", None)
    governmentusertype_unique_id = getattr(governmentusertype, "unique_id", None)

    if not usertype_unique_id:
        return None

    return {
        "usertype_unique_id": usertype_unique_id,
        "staffusertype_unique_id": staffusertype_unique_id,
        "contractorusertype_unique_id": contractorusertype_unique_id,
        "governmentusertype_unique_id": governmentusertype_unique_id,
    }


def _resolve_permissions_for_request(request):
    payload_permissions = getattr(request, "jwt_payload", {}).get("permissions")
    if payload_permissions:
        return payload_permissions

    staff_id = getattr(request.user, "staff_unique_id", None)
    if staff_id:
        local_body_scope = local_body_scope_for_staff(request.user)
        if local_body_scope and local_body_scope.get("local_body_id"):
            cache_key = (
                "module-permissions:local-body:"
                f"{staff_id}:"
                f"{local_body_scope['local_body_type']}:"
                f"{local_body_scope['local_body_id']}"
            )
            permissions = cache.get(cache_key)
            if permissions is None:
                permissions = resolve_intersected_permission_payload(
                    staff_id=staff_id, **local_body_scope
                )["permissions"]
                cache.set(cache_key, permissions, 60)
            return permissions

    filters = _permission_filters_for_user(request.user)
    if not filters:
        return {}

    user_id = getattr(request.user, "staff_unique_id", None) or getattr(
        request.user, "unique_id", None
    ) or getattr(request.user, "pk", None)
    cache_key = (
        "module-permissions:"
        f"{user_id}:"
        f"{filters['usertype_unique_id']}:"
        f"{filters.get('staffusertype_unique_id') or 'none'}:"
        f"{filters.get('contractorusertype_unique_id') or 'none'}"
    )

    permissions = cache.get(cache_key)
    if permissions is None:
        permissions = resolve_permission_payload(**filters)["permissions"]
        cache.set(cache_key, permissions, 60)

    return permissions


# ============================================================
# MIDDLEWARE
# ============================================================

class ModulePermissionMiddleware(MiddlewareMixin):

    def process_view(self, request, view_func, view_args, view_kwargs):

        if request.method == "OPTIONS":
            return None

        if any(request.path.startswith(p) for p in PUBLIC_PREFIXES):
            return None

        if any(request.path.startswith(p) for p in PLATFORM_PREFIXES):
            return None

        if (
            request.method == "POST"
            and f"{request.path.rstrip('/')}/" in COMMON_AUDIT_CREATE_PATHS
        ):
            auth_error = _authenticate_request(request)
            return auth_error

        if any(request.path.startswith(p) for p in AUTH_ONLY_PREFIXES):
            auth_error = _authenticate_request(request)
            return auth_error

        module = _module_from_path(request.path)
        if not module:
            return None

        auth_error = _authenticate_request(request)
        if auth_error:
            return auth_error

        if getattr(request.user, "is_superuser", False):
            return None

        view_class = getattr(view_func, "cls", None)
        if not view_class:
            return None

        exempt_actions = getattr(view_class, "permission_exempt_actions", None)
        if exempt_actions:
            bound_action = (getattr(view_func, "actions", None) or {}).get(
                request.method.lower()
            )
            if bound_action in exempt_actions:
                return None

        permission_resource = getattr(
            view_class,
            "permission_resource",
            view_class.__name__.replace("ViewSet", "")
        )
        route_resource = _route_resource_from_path(request.path, module)

        allowed_resources = MODULE_RESOURCE_ALLOWLIST.get(module, set())
        allowed_resource_keys = {
            self._normalize_permission_key(resource)
            for resource in allowed_resources
        }
        resource_candidates = _resource_allowlist_candidates(
            permission_resource,
            route_resource,
        )
        resource_allowed = any(
            self._normalize_permission_key(candidate) in allowed_resource_keys
            for candidate in resource_candidates
        )

        if not resource_allowed:
            return JsonResponse(
                {
                    "detail": "Permission denied",
                    "module": module,
                    "resource": permission_resource,
                    "route_resource": route_resource,
                    "reason": "Resource not allowed",
                },
                status=403,
            )

        action = HTTP_ACTION_MAP.get(request.method)
        if not action:
            return JsonResponse({"detail": "Invalid HTTP method"}, status=405)

        permissions = _resolve_permissions_for_request(request)
        permission_module = MODULE_PERMISSION_ALIASES.get(module, module)
        allowed_actions = self._resolve_allowed_actions(
            self._lookup_module_permissions(permissions, permission_module),
            permission_resource,
            route_resource,
        )

        if action not in allowed_actions:
            return JsonResponse(
                {
                    "detail": "Permission denied",
                    "module": module,
                    "resource": permission_resource,
                    "action": action,
                },
                status=403,
            )

        return None

    @staticmethod
    def _normalize_permission_key(name):
        if not name:
            return ""
        return re.sub(r"[\W_]+", "", name).lower()

    @classmethod
    def _lookup_module_permissions(cls, permissions, module_name):
        if not permissions:
            return {}

        if module_name in permissions:
            return permissions[module_name]

        target = cls._normalize_permission_key(module_name)
        for key, value in permissions.items():
            if cls._normalize_permission_key(key) == target:
                return value

        return {}

    def _resolve_allowed_actions(self, permissions_map, resource_name, route_resource=None):
        if not permissions_map:
            return []

        resource_candidates = [
            candidate
            for candidate in (
                route_resource,
                resource_name,
                *RESOURCE_PERMISSION_ALIASES.get(resource_name, ()),
            )
            if candidate
        ]

        for candidate in resource_candidates:
            if candidate in permissions_map:
                return permissions_map[candidate]

        for candidate in resource_candidates:
            target = self._normalize_permission_key(candidate)
            for key, actions in permissions_map.items():
                normalized = self._normalize_permission_key(key)
                if normalized == target:
                    return actions
                if normalized.endswith("s") and normalized[:-1] == target:
                    return actions
                if target.endswith("s") and normalized == target[:-1]:
                    return actions
                if target.endswith("y") and normalized == target[:-1] + "ies":
                    return actions
                if normalized.endswith("y") and normalized[:-1] + "ies" == target:
                    return actions

        return []
