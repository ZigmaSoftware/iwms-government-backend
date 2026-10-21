from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.services.audit_dashboard import (
    TRAILS,
    geo_options,
    in_range,
    parse_days,
    summary as build_summary,
    window,
)
from app.utils.pagination import LimitOffsetWithPage
from app.viewsets.superadmin.audits.common_audit_viewset import CommonAuditViewSet
from app.viewsets.superadmin.audits.complaint_audit_viewset import ComplaintAuditViewSet
from app.viewsets.superadmin.audits.login_audit_viewset import LoginAuditViewSet
from app.viewsets.superadmin.audits.permission_audit_viewset import PermissionAuditLogViewSet

# The list viewset of each trail's own audit page. Its _scoped_base_queryset
# is the requester gate the dashboard reuses, so a trail here never shows a
# row that audit's own list would hide.
AUDIT_VIEWSETS = {
    "common": CommonAuditViewSet,
    "login": LoginAuditViewSet,
    "access": PermissionAuditLogViewSet,
    "complaint": ComplaintAuditViewSet,
}


DEFAULT_PAGE_SIZE = 10


def _getlist(query_params, name):
    """Every value sent as ?name=a&name=b or ?name=a,b."""
    return [
        part.strip()
        for value in query_params.getlist(name)
        for part in value.split(",")
        if part.strip()
    ]


class AuditDashboardViewSet(viewsets.ViewSet):
    """
    Read-only Audit Dashboard over the four audit trails. ?module= picks the
    trail (common, login, access, complaint); ?days= the window (7, 30 or
    90); ?district_id= / ?local_body_id= narrow it. Assembled on read by
    app.services.audit_dashboard.

        GET audit-dashboard/summary/          KPIs, per-day trend, breakdown
        GET audit-dashboard/records/          the window's rows, paginated
        GET audit-dashboard/filter-options/   district / local body choices

    Government has no Company/Project: each trail is confined to the
    requester exactly as its own audit list is (a super admin sees
    everything, a scoped staff user their StaffDataScope hierarchy, a staff
    user with no scope row nothing), and district / local body replace the
    private dashboard's company / project scope.
    """

    permission_classes = [IsAuthenticated]
    # Matches the "audit-dashboard" UserScreen in the "audits" module.
    permission_resource = "AuditDashboard"

    def _module(self):
        key = self.request.query_params.get("module") or "common"
        if key not in TRAILS:
            raise ValidationError({"module": f"Choose one of: {', '.join(TRAILS)}."})
        return key, TRAILS[key]

    def _requester_scoped(self, key, trail):
        """The trail's rows the requester may see, via that audit's own
        list viewset."""
        audit_view = AUDIT_VIEWSETS[key](request=self.request, format_kwarg=None)
        return trail.unique(audit_view._scoped_base_queryset())

    def _scoped(self, key, trail):
        params = self.request.query_params
        return trail.narrow(
            self._requester_scoped(key, trail),
            _getlist(params, "district_id"),
            _getlist(params, "local_body_id"),
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        key, trail = self._module()
        days = parse_days(request.query_params.get("days"))
        return Response(build_summary(trail, self._scoped(key, trail), days))

    @action(detail=False, methods=["get"])
    def records(self, request):
        key, trail = self._module()
        days = parse_days(request.query_params.get("days"))
        _, _, start, end, _ = window(days)
        queryset = in_range(trail, self._scoped(key, trail), start, end)

        search = (request.query_params.get("search") or "").strip()
        if search:
            queryset = trail.search(queryset, search)

        paginator = LimitOffsetWithPage()
        # Always a page: without ?limit= the paginator would otherwise
        # return every row of the window unpaginated.
        paginator.default_limit = paginator.default_limit or DEFAULT_PAGE_SIZE
        page = paginator.paginate_queryset(trail.ordered(queryset), request, view=self)
        return paginator.get_paginated_response(trail.rows(page))

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """Districts and local bodies for the scope dropdowns, drawn from
        the selected trail's requester-scoped rows (like the Common Audit
        list's filter-options); local bodies narrow to ?district_id=."""
        key, trail = self._module()
        return Response(geo_options(
            trail,
            self._requester_scoped(key, trail),
            _getlist(request.query_params, "district_id"),
        ))
