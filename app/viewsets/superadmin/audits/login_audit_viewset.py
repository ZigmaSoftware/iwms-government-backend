from rest_framework import filters, viewsets

from app.models.superadmin.audits.login_audit import LoginAudit
from app.serializers.superadmin.audits.login_audit_serializer import LoginAuditSerializer
from app.utils.pagination import LimitOffsetWithPage


class LoginAuditViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get", "head", "options"]
    serializer_class = LoginAuditSerializer
    permission_resource = "LoginAudit"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["username", "ip_address"]
    ordering_fields = ["timestamp", "username"]

    def get_queryset(self):
        return (
            LoginAudit.objects
            .order_by("-timestamp")
        )
