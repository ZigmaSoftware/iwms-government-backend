from django.core.cache import cache
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

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

        local_body_type = (
            self.request.query_params.get("local_body_type")
            or self.request.query_params.get("localBodyType")
        )
        local_body_id = (
            self.request.query_params.get("local_body_id")
            or self.request.query_params.get("localBodyId")
        )
        if local_body_type and local_body_id:
            queryset = queryset.filter(local_body_type=local_body_type, local_body_id=local_body_id)

        permission_owner_kind = (
            self.request.query_params.get("permission_owner_kind")
            or self.request.query_params.get("permissionOwnerKind")
        )
        if permission_owner_kind:
            queryset = queryset.filter(permission_owner_kind=permission_owner_kind)

        staff_id = self.request.query_params.get("staff_id") or self.request.query_params.get("staffId")
        if staff_id:
            queryset = queryset.filter(staff_id=staff_id)

        return queryset

    @action(
        detail=False,
        methods=["post"],
        url_path=r"bulk-sync-by-localbody/(?P<local_body_type>[^/]+)/(?P<local_body_id>[^/.]+)",
    )
    def bulk_sync_by_localbody(self, request, local_body_type, local_body_id):
        """
        Super Admin's Dashboard Widget configuration for a Local Body.
        Upserts each widget's is_enabled/order_no (no duplicate rows on
        repeated saves) and soft-deletes any widget rows not present in the
        incoming payload for this Local Body.
        """
        state_id = request.data.get("stateId") or request.data.get("state_id")
        district_id = request.data.get("districtId") or request.data.get("district_id")
        area_type_id = request.data.get("areaTypeId") or request.data.get("area_type_id")
        widgets = request.data.get("widgets") or []

        with transaction.atomic():
            existing_qs = DashboardWidgetPermission.objects.filter(
                local_body_type=local_body_type,
                local_body_id=local_body_id,
                permission_owner_kind="super_admin",
            )
            existing_by_name = {obj.widget_name: obj for obj in existing_qs}
            incoming_names = set()

            for order_no, widget in enumerate(widgets, start=1):
                widget_name = str(widget.get("widgetName") or widget.get("widget_name") or "").strip()
                if not widget_name:
                    continue
                incoming_names.add(widget_name)
                is_enabled = bool(widget.get("isEnabled", widget.get("is_enabled", True)))

                obj, created = DashboardWidgetPermission.objects.update_or_create(
                    state_id_id=state_id,
                    district_id_id=district_id,
                    area_type_id_id=area_type_id,
                    local_body_type=local_body_type,
                    local_body_id=local_body_id,
                    permission_owner_kind="super_admin",
                    staff_id=None,
                    widget_name=widget_name,
                    is_deleted=False,
                    defaults={
                        "is_enabled": is_enabled,
                        "order_no": widget.get("orderNo", widget.get("order_no", order_no)),
                        "is_active": True,
                    },
                )
                existing_by_name.pop(widget_name, None)

            for widget_name, obj in existing_by_name.items():
                obj.is_deleted = True
                obj.is_active = False
                obj.save(update_fields=["is_deleted", "is_active", "updated_at"])

        cache.clear()
        return Response(
            {"message": "Dashboard widgets saved successfully"},
            status=status.HTTP_200_OK,
        )
