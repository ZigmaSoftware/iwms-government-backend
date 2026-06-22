from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from app.models.role_assigns.contractorUserType import ContractorUserType
from app.models.role_assigns.governmentStaffUserType import GovernmentStaffUserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.role_assigns.userType import UserType
from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.userscreencolumn import UserScreenColumn
from app.serializers.screen_managements.companyuserscreencolumnpermission_serializer import (
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
            can_view = True,
        ).select_related(
            "usertype_id",
            "staffusertype_id",
            "contractorusertype_id",
            "governmentusertype_id",
            "userscreen_id",
            "column_id",
        )

        userscreen_id = self.request.query_params.get("userscreen_id")
        if userscreen_id:
            qs = qs.filter(userscreen_id_id=userscreen_id)

        staffusertype_id = self.request.query_params.get("staffusertype_id")
        if staffusertype_id:
            qs = qs.filter(staffusertype_id_id=staffusertype_id)

        contractorusertype_id = (
            self.request.query_params.get("contractorusertype_id")
            or self.request.query_params.get("contractorUserTypeId")
        )
        if contractorusertype_id:
            qs = qs.filter(contractorusertype_id_id=contractorusertype_id)

        governmentusertype_id = (
            self.request.query_params.get("governmentusertype_id")
            or self.request.query_params.get("governmentUserTypeId")
        )
        if governmentusertype_id:
            qs = qs.filter(governmentusertype_id_id=governmentusertype_id)

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
        write_ser = UserScreenColumnPermissionWriteSerializer(data=request.data)
        write_ser.is_valid(raise_exception=True)
        vd = write_ser.validated_data

        # Resolve FK objects
        userscreen = UserScreen.objects.get(unique_id=vd["userscreen_id"])
        column = UserScreenColumn.objects.get(unique_id=vd["column_id"])

        staffusertype = None
        staffusertype_id_str = vd.get("staffusertype_id") or ""
        if staffusertype_id_str:
            staffusertype = StaffUserType.objects.filter(
                unique_id=staffusertype_id_str
            ).first()

        contractorusertype = None
        contractorusertype_id_str = vd.get("contractorusertype_id") or ""
        if contractorusertype_id_str:
            contractorusertype = ContractorUserType.objects.filter(
                unique_id=contractorusertype_id_str
            ).first()

        governmentusertype = None
        governmentusertype_id_str = vd.get("governmentusertype_id") or ""
        if governmentusertype_id_str:
            governmentusertype = GovernmentStaffUserType.objects.filter(
                unique_id=governmentusertype_id_str
            ).first()

        usertype = None
        usertype_id_str = vd.get("usertype_id") or ""
        if usertype_id_str:
            usertype = UserType.objects.filter(unique_id=usertype_id_str).first()

        account = None

        with transaction.atomic():
            instance, created = CompanyUserScreenColumnPermission.objects.get_or_create(
                staffusertype_id=staffusertype,
                contractorusertype_id=contractorusertype,
                governmentusertype_id=governmentusertype,
                usertype_id=usertype,
                userscreen_id=userscreen,
                column_id=column,
                is_deleted=False,
                defaults={
                    "can_view": vd.get("is_active", True),
                    "order_no": vd.get("order_no", 1),
                    "description": vd.get("description") or "",
                    "created_by": account,
                },
            )

            if not created:
                # Update can_view in-place; never create a duplicate
                instance.can_view = vd.get("is_active", True)
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
        instance = self.get_object()
        previous_data = self._serialize_instance(instance)

        is_active = request.data.get("is_active")
        if is_active is not None:
            instance.can_view = bool(is_active)

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
