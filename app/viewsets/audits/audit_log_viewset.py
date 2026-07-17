from rest_framework import viewsets

from app.models.audits.audit_log import AuditLog
from app.serializers.audits.audit_log_serializer import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    http_method_names = ["get", "head", "options"]
    serializer_class = AuditLogSerializer
    permission_resource = "AuditLog"

    def get_queryset(self):
        return (
            AuditLog.objects
            .select_related(
                "user_id",
                "staffusertype_id",
                "mainscreen_id",
                "userscreen_id",
                "userscreenaction_id",
            )
            .order_by("-timestamp")
        )
