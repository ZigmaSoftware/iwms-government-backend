from rest_framework import viewsets
from rest_framework.filters import OrderingFilter

from app.models.screen_managements.dashboardwidgetpermission import DashboardWidgetPermission
from app.serializers.screen_managements.dashboardwidgetpermission_serializer import (
    DashboardWidgetPermissionSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin


class DashboardWidgetPermissionViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = DashboardWidgetPermissionSerializer
    lookup_field = "unique_id"
    permission_resource = "DashboardWidgetPermission"

    AUDIT_MODULE = "screen-managements"
    AUDIT_ENDPOINT = "dashboard-widget-permissions"

    filter_backends = [OrderingFilter]
    ordering_fields = ["order_no", "created_at", "updated_at"]
    ordering = ["order_no"]

    def get_queryset(self):
        queryset = DashboardWidgetPermission.objects.filter(
            is_deleted=False,
        ).select_related(
            "usertype_id",
            "staffusertype_id",
            "contractorusertype_id",
            "governmentusertype_id",
        )

        staffusertype_id = self.request.query_params.get("staffusertype_id")
        if staffusertype_id:
            queryset = queryset.filter(staffusertype_id_id=staffusertype_id)

        contractorusertype_id = (
            self.request.query_params.get("contractorusertype_id")
            or self.request.query_params.get("contractorUserTypeId")
        )
        if contractorusertype_id:
            queryset = queryset.filter(contractorusertype_id_id=contractorusertype_id)

        governmentusertype_id = (
            self.request.query_params.get("governmentusertype_id")
            or self.request.query_params.get("governmentUserTypeId")
        )
        if governmentusertype_id:
            queryset = queryset.filter(governmentusertype_id_id=governmentusertype_id)

        return queryset
