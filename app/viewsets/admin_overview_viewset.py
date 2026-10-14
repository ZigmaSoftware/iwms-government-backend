import copy
import logging

from django.http import QueryDict
from django.urls import Resolver404, resolve
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.middleware.module_permission_middleware import ModulePermissionMiddleware
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.utils.plain_ref import ref_q

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1/"

# Admin dashboard (AdminHome) card key → list route. Only counts are needed
# there, so instead of the browser downloading every one of these tables
# (customers, bins, 20k+ panchayats, ...) this endpoint returns their sizes
# in a single request.
COUNT_ROUTES = {
    "continents": "common-masters/continents",
    "countries": "common-masters/countries",
    "states": "common-masters/states",
    "districts": "masters/districts",
    "panchayats": "masters/panchayat",
    "departments": "masters/departments",
    "designations": "masters/designations",
    "areaTypes": "masters/areatypes",
    "hierarchies": "masters/hierarchy",
    "properties": "waste-types/properties",
    "subProperties": "waste-types/subproperties",
    "collectionPoints": "schedule-setup/collection-points",
    "wasteTypes": "waste-types/wastetypes",
    "bins": "waste-types/bins",
    "users": "user-creations/users-creation",
    "userTypes": "role-assigns/user-type",
    "staffUserTypes": "role-assigns/staffusertypes",
    "staff": "user-creations/staffcreation",
    "customers": "customer-masters/customercreations",
    "vehicleTypes": "transport-masters/vehicle-type",
    "vehicles": "transport-masters/vehicle-creation",
    "fuels": "transport-masters/fuels",
    "wasteCollections": "schedule-operations/wastecollections",
    "complaints": "complaint-ticket/tickets",
    "feedbacks": "customer-masters/feedbacks",
    "mainCategories": "complaint-ticket/categories",
    "subCategories": "complaint-ticket/subcategories",
    "mainScreenTypes": "screen-managements/mainscreentype",
    "mainScreens": "screen-managements/mainscreens",
    "userScreens": "screen-managements/userscreens",
    "screenActions": "screen-managements/userscreen-action",
    "screenPermissions": "screen-managements/userscreenpermissions",
    "columnPermissions": "screen-managements/column-permissions",
}

# Keys whose "active" figure the dashboard also shows.
ACTIVE_COUNT_KEYS = {"users", "staff", "bins", "vehicles"}


def _has_field(model, name):
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


class AdminOverviewViewSet(ViewSet):
    """GET /dashboard/admin-overview/ → {"counts": {...}, "active": {...}}.

    Each count goes through the same gates as the resource's own list
    endpoint: ModulePermissionMiddleware is evaluated against that route
    (a denied resource reports null, like a failed request did before), and
    rows come from the target viewset's own get_queryset(), so requester
    data scoping is identical. Viewsets are not dispatched, so these
    sub-counts don't consume the user's API throttle budget.
    """

    throttle_scope = "admin_overview"
    permission_classes = [IsAuthenticated]

    def list(self, request):
        permission_gate = ModulePermissionMiddleware(get_response=lambda r: None)
        counts, active = {}, {}

        for key, route in COUNT_ROUTES.items():
            queryset = self._scoped_queryset(request, route, permission_gate)
            if queryset is None:
                counts[key] = None
                continue
            try:
                counts[key] = queryset.count()
                if key in ACTIVE_COUNT_KEYS:
                    model = queryset.model
                    active[key] = (
                        queryset.filter(is_active=True).count()
                        if _has_field(model, "is_active")
                        else counts[key]
                    )
                elif key == "complaints":
                    active[key] = queryset.exclude(
                        ref_q("status_id", ComplaintStatus, is_final=True)
                    ).count()
            except Exception:
                logger.exception("admin-overview: count failed for %s", route)
                counts[key] = None

        return Response({"counts": counts, "active": active})

    @staticmethod
    def _scoped_queryset(request, route, permission_gate):
        path = f"{API_PREFIX}{route}/"
        try:
            match = resolve(path)
        except Resolver404:
            logger.warning("admin-overview: unknown route %s", path)
            return None

        view_func = match.func
        view_class = getattr(view_func, "cls", None)
        if view_class is None:
            return None

        # Ask the module-permission middleware whether a plain GET on this
        # resource's list route would be allowed for this user.
        sub_request = copy.copy(request._request)
        sub_request.path = sub_request.path_info = path
        sub_request.method = "GET"
        sub_request.GET = QueryDict("")
        if permission_gate.process_view(sub_request, view_func, (), {}) is not None:
            return None

        try:
            view = view_class(**(getattr(view_func, "initkwargs", None) or {}))
            view.action_map = getattr(view_func, "actions", None) or {}
            view.action = "list"
            view.request = request
            view.args, view.kwargs = (), {}
            view.format_kwarg = None
            return view.get_queryset()
        except Exception:
            logger.exception("admin-overview: get_queryset failed for %s", route)
            return None
