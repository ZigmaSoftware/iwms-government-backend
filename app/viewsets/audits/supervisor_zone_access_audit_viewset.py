from rest_framework.viewsets import ReadOnlyModelViewSet

from app.models.audits.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from app.serializers.audits.supervisor_zone_access_audit_serializer import (
    SupervisorZoneAccessAuditSerializer
)


class SupervisorZoneAccessAuditViewSet(ReadOnlyModelViewSet):
    """
    Read-only audit log for supervisor zone access changes.
    Authorization enforced via JWT + ModulePermissionMiddleware.
    """

    queryset = SupervisorZoneAccessAudit.objects.all().order_by("-created_at")
    serializer_class = SupervisorZoneAccessAuditSerializer

    # Required for middleware permission resolution
    permission_resource = "SupervisorZoneAccessAudit"
