from datetime import datetime, time

from django.db.models import Q
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware
from rest_framework import filters, viewsets

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.audits.login_audit import LoginAudit
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.superadmin.audits.login_audit_serializer import LoginAuditSerializer
from app.utils.hierarchy import (
    FLAT_GEO_QUERY_FIELDS,
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
    local_body_scope_for_staff,
)
from app.utils.pagination import LimitOffsetWithPage


class LoginAuditViewSet(viewsets.ReadOnlyModelViewSet):
    throttle_scope = "login_audit"
    http_method_names = ["get", "head", "options"]
    serializer_class = LoginAuditSerializer
    permission_resource = "LoginAudit"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = [
        "unique_id",
        "module_name",
        "username",
        "user_unique_id",
        "ip_address",
        "user_agent",
        "reason",
    ]
    ordering_fields = ["timestamp", "module_name", "username", "ip_address", "success"]

    @staticmethod
    def _getlist(query_params, *names):
        """Every value sent under any of `names`, as repeated keys or one
        comma-separated value."""
        return [
            part.strip()
            for name in names
            for value in query_params.getlist(name)
            for part in value.split(",")
            if part.strip()
        ]

    def _scoped_base_queryset(self):
        """
        Hierarchy gate. A super admin sees every login; a scoped staff user
        sees only logins of the staff and customers inside their own
        StaffDataScope (the government counterpart of private's company
        pinning); a staff user with no scope row sees nothing. Failed
        attempts carry no user_unique_id, so they are matched on the
        username that was tried.
        """
        queryset = LoginAudit.objects.order_by("-timestamp")
        user = self.request.user
        if getattr(user, "is_superuser", False):
            return queryset
        if local_body_scope_for_staff(user) is None:
            # No resolvable scope: same deny-by-default rule as every other
            # scoped endpoint (non-staff callers are already gated by the
            # module permission middleware).
            return queryset.none()

        staff = filter_flat_geo_queryset_by_requester_scope(
            Staffcreation.objects.all(), user
        )
        customers = filter_flat_geo_queryset_by_requester_scope(
            CustomerCreation.objects.all(), user
        )
        return queryset.filter(
            Q(user_unique_id__in=staff.values("staff_unique_id"))
            | Q(user_unique_id__in=customers.values("unique_id"))
            | Q(
                user_unique_id__isnull=True,
                username__in=staff.exclude(username__isnull=True).values("username"),
            )
            | Q(
                user_unique_id__isnull=True,
                username__in=customers.exclude(username__isnull=True).values("username"),
            )
        )

    @staticmethod
    def _filter_by_geo_params(queryset, params):
        """
        The list page's location filter (?state_id=/.../?panchayat_id=). A
        login row has no geo of its own, so it matches through the account
        that logged in: staff and customers carry the flat geo columns. Only
        narrows, on top of the scope gate above.
        """
        if not any(params.get(field) for field in FLAT_GEO_QUERY_FIELDS):
            return queryset
        staff = filter_flat_geo_queryset_by_params(Staffcreation.objects.all(), params)
        customers = filter_flat_geo_queryset_by_params(CustomerCreation.objects.all(), params)
        return queryset.filter(
            Q(user_unique_id__in=staff.values("staff_unique_id"))
            | Q(user_unique_id__in=customers.values("unique_id"))
        )

    def get_queryset(self):
        queryset = self._scoped_base_queryset()
        params = self.request.query_params

        module_names = self._getlist(params, "module_name", "module")
        if module_names:
            queryset = queryset.filter(module_name__in=module_names)

        # "true"/"false" — isolates failed attempts from successful logins.
        success = params.get("success")
        if success not in (None, ""):
            queryset = queryset.filter(
                success=success.lower() in ("1", "true", "yes")
            )

        user_unique_id = params.get("user_unique_id")
        if user_unique_id:
            queryset = queryset.filter(user_unique_id=user_unique_id)

        username = params.get("username")
        if username:
            queryset = queryset.filter(username__icontains=username)

        ip_address = params.get("ip_address")
        if ip_address:
            queryset = queryset.filter(ip_address__icontains=ip_address)

        # Date range on timestamp — date_from is inclusive from 00:00:00,
        # date_to is inclusive through 23:59:59 of that day.
        date_from = parse_date(params.get("date_from") or "")
        if date_from:
            queryset = queryset.filter(
                timestamp__gte=make_aware(datetime.combine(date_from, time.min))
            )
        date_to = parse_date(params.get("date_to") or "")
        if date_to:
            queryset = queryset.filter(
                timestamp__lte=make_aware(datetime.combine(date_to, time.max))
            )

        return self._filter_by_geo_params(queryset, params)
