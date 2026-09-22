from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.serializers.superadmin.audits.permission_audit_serializer import (
    PermissionAuditLogSerializer,
)
from app.utils.pagination import LimitOffsetWithPage


class PermissionAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit trail of role/permission grant changes (User Access
    Audit). Writes happen only via the post_save signal on
    UserScreenPermission (app/signals/permission_signals.py) — this viewset
    never creates or edits rows."""

    throttle_scope = "permission_audit"
    permission_classes = [IsAuthenticated]

    queryset = PermissionAuditLog.objects.all().select_related(
        "staffusertype",
        "usertype",
        "contractorusertype",
        "governmentusertype",
        "mainscreen",
        "userscreen",
        "userscreenaction",
        "updated_by",
    )
    serializer_class = PermissionAuditLogSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["mainscreen__mainscreen_name", "userscreen__userscreen_name", "action_type"]
    ordering_fields = ["timestamp", "action_type"]

    def get_queryset(self):
        queryset = super().get_queryset()

        mainscreen_id = self.request.query_params.get("mainscreen_id")
        staffusertype_id = self.request.query_params.get("staffusertype_id")
        action_type = self.request.query_params.get("action_type")

        if mainscreen_id:
            queryset = queryset.filter(mainscreen_id=mainscreen_id)
        if staffusertype_id:
            queryset = queryset.filter(staffusertype_id=staffusertype_id)
        if action_type:
            queryset = queryset.filter(action_type=action_type)

        return queryset
