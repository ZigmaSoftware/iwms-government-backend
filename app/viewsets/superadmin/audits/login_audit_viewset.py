from rest_framework import viewsets

from app.models.superadmin.audits.login_audit import LoginAudit
from app.serializers.superadmin.audits.login_audit_serializer import LoginAuditSerializer


class LoginAuditViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get", "head", "options"]
    serializer_class = LoginAuditSerializer
    permission_resource = "LoginAudit"

    def get_queryset(self):
        return (
            LoginAudit.objects
            .order_by("-timestamp")
        )
