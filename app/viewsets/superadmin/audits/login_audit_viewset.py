from rest_framework import filters, viewsets

from app.models.superadmin.audits.login_audit import LoginAudit
from app.serializers.superadmin.audits.login_audit_serializer import LoginAuditSerializer
from app.utils.pagination import LimitOffsetWithPage


class LoginAuditViewSet(viewsets.ReadOnlyModelViewSet):
    throttle_scope = "login_audit"
    http_method_names = ["get", "head", "options"]
    serializer_class = LoginAuditSerializer
    permission_resource = "LoginAudit"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["module_name", "username", "ip_address", "reason"]
    ordering_fields = ["timestamp", "module_name", "username"]

    def get_queryset(self):
        queryset = (
            LoginAudit.objects
            .order_by("-timestamp")
        )
        raw_values = [
            *self.request.query_params.getlist("module_name"),
            *self.request.query_params.getlist("module"),
        ]
        module_names = [
            part.strip()
            for value in raw_values
            for part in value.split(",")
            if part.strip()
        ]
        if module_names:
            queryset = queryset.filter(module_name__in=module_names)
        return queryset
