from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from app.models.superadmin.screen_management.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn
from app.serializers.superadmin.screen_management.companyuserscreencolumnpermission_serializer import (
    UserScreenColumnPermissionSerializer,
    UserScreenColumnPermissionWriteSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin


class CompanyUserScreenColumnPermissionViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """
    Dedicated CRUD API for CompanyUserScreenColumnPermission.

    Endpoints:
      GET    /screen-managements/column-permissions/              → list (grouped by userscreen_id)
      GET    /screen-managements/column-permissions/{unique_id}/  → retrieve
      POST   /screen-managements/column-permissions/              → create (get_or_create, no duplicates)
      PATCH  /screen-managements/column-permissions/{unique_id}/  → update (can_view only)
    """

    serializer_class = UserScreenColumnPermissionSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "screen-managements"
    AUDIT_ENDPOINT = "company-user-screen-column-permissions"
    permission_resource = "column-permissions"

    filter_backends = [OrderingFilter]
    ordering_fields = ["order_no", "created_at"]
    ordering = ["order_no"]

    # ---------------------------------------------------------
    # Queryset — company-scoped, optimised selects
    # ---------------------------------------------------------

    def get_queryset(self):
        qs = CompanyUserScreenColumnPermission.objects.filter(
            is_deleted=False,
        ).select_related(
            "state_id",
            "district_id",
            "area_type_id",
            "userscreen_id",
            "column_id",
        )

        userscreen_id = self.request.query_params.get("userscreen_id")
        if userscreen_id:
            qs = qs.filter(userscreen_id_id=userscreen_id)

        local_body_type = (
            self.request.query_params.get("local_body_type")
            or self.request.query_params.get("localBodyType")
        )
        local_body_id = (
            self.request.query_params.get("local_body_id")
            or self.request.query_params.get("localBodyId")
        )
        if local_body_type and local_body_id:
            qs = qs.filter(local_body_type=local_body_type, local_body_id=local_body_id)

        state_id = self.request.query_params.get("state_id") or self.request.query_params.get("stateId")
        if state_id:
            qs = qs.filter(state_id_id=state_id)
        district_id = self.request.query_params.get("district_id") or self.request.query_params.get("districtId")
        if district_id:
            qs = qs.filter(district_id_id=district_id)
        area_type_id = self.request.query_params.get("area_type_id") or self.request.query_params.get("areaTypeId")
        if area_type_id:
            qs = qs.filter(area_type_id_id=area_type_id)

        return qs

    # ---------------------------------------------------------
    # List — grouped by userscreen_id
    # ---------------------------------------------------------

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        userscreen_id = request.query_params.get("userscreen_id", "")
        serializer = UserScreenColumnPermissionSerializer(qs, many=True)
        return Response(
            {
                "userscreen_id": userscreen_id,
                "column_permissions": serializer.data,
            }
        )

    # ---------------------------------------------------------
    # Retrieve — single record wrapped in grouped format
    # ---------------------------------------------------------

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = UserScreenColumnPermissionSerializer(instance)
        return Response(
            {
                "userscreen_id": str(instance.userscreen_id_id),
                "userscreen_name": instance.userscreen_id.userscreen_name,
                "column_permissions": [serializer.data],
            }
        )

    # ---------------------------------------------------------
    # Create — get_or_create prevents duplicate records
    # ---------------------------------------------------------

    def create(self, request, *args, **kwargs):
        if not getattr(request.user, "is_superuser", False):
            raise PermissionDenied("Only Super Admin can configure Field Permission.")

        write_ser = UserScreenColumnPermissionWriteSerializer(data=request.data)
        write_ser.is_valid(raise_exception=True)
        vd = write_ser.validated_data

        # Resolve FK objects
        userscreen = UserScreen.objects.get(unique_id=vd["userscreen_id"])
        column = UserScreenColumn.objects.get(unique_id=vd["column_id"])

        account = None

        with transaction.atomic():
            instance, created = CompanyUserScreenColumnPermission.objects.get_or_create(
                state_id_id=vd.get("state_id"),
                district_id_id=vd.get("district_id"),
                area_type_id_id=vd.get("area_type_id"),
                local_body_type=vd["local_body_type"],
                local_body_id=vd["local_body_id"],
                userscreen_id=userscreen,
                column_id=column,
                is_deleted=False,
                defaults={
                    "field_permission_state": vd.get("field_permission_state"),
                    "order_no": vd.get("order_no", 1),
                    "description": vd.get("description") or "",
                    "created_by": account,
                },
            )

            if not created:
                instance.field_permission_state = vd.get("field_permission_state")
                if hasattr(instance, "updated_by"):
                    instance.updated_by = account
                instance.save()

        instance.refresh_from_db()

        new_data = self._serialize_instance(instance)
        self.log_audit(
            request,
            instance=instance,
            previous_data=None if created else new_data,
            new_data=new_data,
        )

        read_ser = UserScreenColumnPermissionSerializer(instance)
        return Response(
            {
                "userscreen_id": str(vd["userscreen_id"]),
                "column_permissions": [read_ser.data],
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    # ---------------------------------------------------------
    # Update / Partial-Update — only toggles can_view
    # ---------------------------------------------------------

    def update(self, request, *args, **kwargs):
        if not getattr(request.user, "is_superuser", False):
            raise PermissionDenied("Only Super Admin can configure Field Permission.")

        instance = self.get_object()
        previous_data = self._serialize_instance(instance)

        is_active = request.data.get("is_active")
        if is_active is not None:
            instance.can_view = bool(is_active)
        field_permission_state = request.data.get("field_permission_state")
        if field_permission_state is not None:
            instance.field_permission_state = field_permission_state

        account = None
        if hasattr(instance, "updated_by"):
            instance.updated_by = account

        instance.save()

        self.log_audit(
            request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )

        read_ser = UserScreenColumnPermissionSerializer(instance)
        return Response(
            {
                "userscreen_id": str(instance.userscreen_id_id),
                "column_permissions": [read_ser.data],
            }
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)
