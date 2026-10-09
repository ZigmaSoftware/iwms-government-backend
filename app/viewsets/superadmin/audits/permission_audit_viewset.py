import importlib

from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.superadmin.audits.permission_audit_serializer import (
    LOCAL_BODY_MODELS,
    PermissionAuditLogListSerializer,
    PermissionAuditLogSerializer,
    _resolve_local_body_name,
)
from app.utils.hierarchy import (
    _local_body_ids_by_level,
    _staff_scope,
    _unscoped_result,
    filter_flat_geo_queryset_by_requester_scope,
    filter_staff_queryset_by_requester_scope,
)
from app.utils.pagination import LimitOffsetWithPage

# Per-grant rows (GRANT_CHANGE) belong under the access-save source that now
# records the same grants, so filtering by a source keeps its older rows.
LEGACY_SOURCE_FILTERS = {
    "STAFF_ACCESS": Q(source="GRANT_CHANGE", permission_owner_kind="staff"),
    "LOCAL_BODY_SCREEN": Q(source="GRANT_CHANGE", local_body_id__isnull=False)
    & ~Q(permission_owner_kind="staff"),
    "ROLE_SCREEN": Q(source="GRANT_CHANGE", local_body_id__isnull=True)
    & ~Q(permission_owner_kind="staff"),
}


def _csv(value):
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _local_body_model(level):
    module_path, class_name = LOCAL_BODY_MODELS[level].rsplit(".", 1)
    return getattr(importlib.import_module(module_path), class_name)


class PermissionAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only trail of screen/action permission grant changes (User Access
    Audit). Every screen that grants permissions writes one row per save,
    holding the access before and after it (app/utils/permission_snapshot.py);
    rows from before that, and writes made outside those screens, are the
    per-grant rows of the UserScreenPermission post_save signal
    (app/signals/permission_signals.py). This viewset never creates or edits
    rows."""

    throttle_scope = "permission_audit"
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]
    # Matches the "permission-audit" UserScreen, named like LoginAudit /
    # CommonAudit in ModulePermissionMiddleware.
    permission_resource = "PermissionAudit"
    serializer_class = PermissionAuditLogSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = [
        "source",
        "target_id",
        "staff_id",
        "local_body_id",
        "mainscreen_id",
        "userscreen_id",
        "userscreenaction_id",
        "updated_by_id",
        "action_type",
        "http_method",
    ]
    ordering_fields = ["timestamp", "action_type", "http_method"]

    def get_serializer_class(self):
        if getattr(self, "action", None) == "list":
            return PermissionAuditLogListSerializer
        return super().get_serializer_class()

    # ------------------------------------------------------------------
    # Requester scope
    # ------------------------------------------------------------------
    @staticmethod
    def _geo_q(scope):
        """Rows whose grant sits in the requester's local bodies, or, for a
        District/State-level requester, anywhere beneath that boundary.
        None means the scope sets no boundary at all."""
        by_level = _local_body_ids_by_level(scope)
        if by_level:
            q = Q()
            for level, ids in by_level.items():
                q |= Q(local_body_type=level, local_body_id__in=ids)
            return q

        for scope_field, row_field in (("district", "district_id"), ("state", "state_id")):
            value = getattr(scope, scope_field, None)
            if not value:
                continue
            # Older per-grant rows carry only the local body, so match the
            # local bodies inside the boundary as well as the row's own geo.
            q = Q(**{row_field: value})
            for level in LOCAL_BODY_MODELS:
                q |= Q(
                    local_body_type=level,
                    local_body_id__in=_local_body_model(level)
                    .objects.filter(**{row_field: value})
                    .values("unique_id"),
                )
            return q
        return None

    def _scoped_base_queryset(self):
        """
        Hierarchy gate, the government way: a super admin sees every row; a
        staff user sees grants inside their own StaffDataScope (local bodies,
        or everything under their District/State) plus the access of any
        staff member / customer they can see; a staff user with no scope row
        sees nothing (see hierarchy._unscoped_result).
        """
        queryset = PermissionAuditLog.objects.all().order_by("-timestamp")
        user = self.request.user

        if getattr(user, "is_superuser", False):
            return queryset

        scope = _staff_scope(user)
        if not scope:
            return _unscoped_result(queryset, user)

        geo_q = self._geo_q(scope)
        if geo_q is None:
            return queryset

        staff_ids = filter_staff_queryset_by_requester_scope(
            Staffcreation.objects.all(), user
        ).values("staff_unique_id")
        customer_ids = filter_flat_geo_queryset_by_requester_scope(
            CustomerCreation.objects.all(), user
        ).values("unique_id")
        return queryset.filter(
            geo_q
            | Q(staff_id__in=staff_ids)
            | Q(source="CUSTOMER_ACCESS", target_id__in=customer_ids)
        )

    @staticmethod
    def _filter_by_geo_params(queryset, params):
        """
        The list page's location filter (?state_id=/?district_id=/
        ?area_type_id=/?corporation_id=/...). A local-body param matches the
        grant's own local body; a State/District/Area type matches the row's
        own geo or any local body inside it (older per-grant rows carry only
        the local body), the same widening `_geo_q` uses for scope.
        """
        for row_field in ("state_id", "district_id", "area_type_id"):
            value = params.get(row_field)
            if not value:
                continue
            q = Q(**{row_field: value})
            for level in LOCAL_BODY_MODELS:
                q |= Q(
                    local_body_type=level,
                    local_body_id__in=_local_body_model(level)
                    .objects.filter(**{row_field: value})
                    .values("unique_id"),
                )
            queryset = queryset.filter(q)
        for level in LOCAL_BODY_MODELS:
            value = params.get(f"{level}_id")
            if value:
                queryset = queryset.filter(local_body_type=level, local_body_id=value)
        return queryset

    # ------------------------------------------------------------------
    # Queryset
    # ------------------------------------------------------------------
    def get_queryset(self):
        queryset = self._scoped_base_queryset()
        params = self.request.query_params

        sources = {s.upper() for s in _csv(params.get("source"))}
        if sources:
            source_q = Q(source__in=sources)
            for source in sources:
                legacy = LEGACY_SOURCE_FILTERS.get(source)
                if legacy is not None:
                    source_q |= legacy
            queryset = queryset.filter(source_q)

        local_body_type = params.get("local_body_type")
        if local_body_type:
            queryset = queryset.filter(local_body_type=local_body_type)

        local_body_ids = _csv(params.get("local_body_id"))
        if local_body_ids:
            queryset = queryset.filter(local_body_id__in=local_body_ids)

        mainscreen_ids = _csv(params.get("mainscreen_id"))
        if mainscreen_ids:
            queryset = queryset.filter(mainscreen_id__in=mainscreen_ids)

        for field in ("staffusertype_id", "governmentusertype_id"):
            values = _csv(params.get(field))
            if values:
                queryset = queryset.filter(**{f"{field}__in": values})

        target_id = params.get("target_id")
        if target_id:
            queryset = queryset.filter(Q(target_id=target_id) | Q(staff_id=target_id))

        action_type = params.get("action_type")
        if action_type:
            queryset = queryset.filter(action_type=action_type.upper())

        date_from = parse_date(params.get("date_from") or "")
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)

        date_to = parse_date(params.get("date_to") or "")
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)

        return self._filter_by_geo_params(queryset, params)

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """
        Source / local body / main screen choices for the list page's
        dropdowns, drawn from the scoped queryset so a scoped user is never
        offered a local body outside their hierarchy.
        """
        # order_by() clears Meta.ordering so DISTINCT applies to the columns.
        unordered = self._scoped_base_queryset().order_by()

        local_bodies = []
        for level, local_body_id in (
            unordered.exclude(local_body_id__isnull=True)
            .exclude(local_body_type__isnull=True)
            .values_list("local_body_type", "local_body_id")
            .distinct()
        ):
            if level not in LOCAL_BODY_MODELS:
                continue
            name = _resolve_local_body_name(level, local_body_id) or local_body_id
            local_bodies.append({
                "unique_id": local_body_id,
                "name": f"{name} ({level.replace('_', ' ').title()})",
                "local_body_type": level,
            })
        local_bodies.sort(key=lambda o: o["name"].lower())

        mainscreen_ids = [
            v for v in unordered.values_list("mainscreen_id", flat=True).distinct() if v
        ]
        mainscreens = sorted(
            (
                {"unique_id": uid, "name": name or uid}
                for uid, name in MainScreen.objects.filter(
                    unique_id__in=mainscreen_ids
                ).values_list("unique_id", "mainscreen_name")
            ),
            key=lambda o: o["name"].lower(),
        )

        return Response({
            "sources": [
                {"unique_id": value, "name": label}
                for value, label in PermissionAuditLog.SOURCE_CHOICES
                if value in PermissionAuditLog.CURRENT_SOURCES
            ],
            "local_bodies": local_bodies,
            "mainscreens": mainscreens,
        })
