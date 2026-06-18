from django.db import transaction
from django.utils import timezone

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from app.models.user_creations.staffcreation import Staffcreation
from app.permissions.platform import SuperAdminApprovalPermission
from app.serializers.user_creations.staffcreation_serializer import (
    StaffApprovalActionSerializer,
    StaffcreationSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets


class StaffcreationViewset(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = Staffcreation.objects.select_related(
        "personal_details",
        "department_id",
        "designation_id",
        "staffusertype_id",
        "contractorusertype_id",
    ).all()
    serializer_class = StaffcreationSerializer
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_resource = "StaffCreation"
    lookup_field = "staff_unique_id"

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "staffcreation"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "employee_name",
        "staff_unique_id",
        "site_name",
        "department",
        "designation",
        "department_id__department_name",
        "department_id__department_code",
        "designation_id__designation_name",
        "designation_id__designation_group",
    ]
    ordering_fields = ["staff_unique_id", "employee_name", "created_at"]

    approval_action_names = {"approve", "reject", "suspend", "reactivate"}

    def get_permissions(self):
        if getattr(self, "action", None) in self.approval_action_names:
            return [SuperAdminApprovalPermission()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = Staffcreation.objects.select_related(
            "personal_details",
            "department_id",
            "designation_id",
            "staffusertype_id",
            "contractorusertype_id",
        )

        site_name = self.request.query_params.get("site_name", None)
        employee_name = self.request.query_params.get("employee_name", None)
        active_status = self.request.query_params.get("active_status", None)
        salary_type = self.request.query_params.get("salary_type", None)
        department_id = self.request.query_params.get("department_id", None)
        staffusertype_id = self.request.query_params.get("staffusertype_id", None)
        contractorusertype_id = self.request.query_params.get("contractorusertype_id", None)
        approval_status = self.request.query_params.get("approval_status", None)
        login_enabled = self.request.query_params.get("login_enabled", None)

        if site_name:
            queryset = queryset.filter(site_name__icontains=site_name)

        if employee_name:
            queryset = queryset.filter(employee_name__icontains=employee_name)

        if active_status in ["0", "1"]:
            queryset = queryset.filter(active_status=active_status == "1")

        if salary_type:
            queryset = queryset.filter(salary_type__icontains=salary_type)

        if department_id:
            queryset = queryset.filter(department_id__unique_id=department_id)

        if staffusertype_id:
            queryset = queryset.filter(staffusertype_id__unique_id=staffusertype_id)

        if contractorusertype_id:
            queryset = queryset.filter(contractorusertype_id__unique_id=contractorusertype_id)

        if approval_status:
            queryset = queryset.filter(approval_status=approval_status.upper())

        if login_enabled in ["0", "1", "true", "false", "True", "False"]:
            queryset = queryset.filter(login_enabled=str(login_enabled).lower() in ["1", "true"])

        return queryset.order_by("-created_at")

    def _approval_response(self, staff, message):
        return Response(
            {
                "status": True,
                "message": message,
                "data": {
                    "staff_unique_id": staff.staff_unique_id,
                    "employee_name": staff.employee_name,
                    "approval_status": staff.approval_status,
                    "login_enabled": staff.login_enabled,
                    "approved_by": getattr(staff.approved_by, "unique_id", None),
                    "approved_at": staff.approved_at,
                    "rejected_reason": staff.rejected_reason,
                },
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, staff_unique_id=None):
        staff = self.get_object()
        staff.approval_status = Staffcreation.APPROVAL_APPROVED
        staff.login_enabled = True
        staff.approved_by = request.user
        staff.approved_at = timezone.now()
        staff.rejected_reason = None
        staff.save(
            update_fields=[
                "approval_status",
                "login_enabled",
                "approved_by",
                "approved_at",
                "rejected_reason",
                "updated_at",
            ]
        )
        return self._approval_response(staff, "User approved successfully")

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, staff_unique_id=None):
        serializer = StaffApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = self.get_object()
        staff.approval_status = Staffcreation.APPROVAL_REJECTED
        staff.login_enabled = False
        staff.approved_by = None
        staff.approved_at = None
        staff.rejected_reason = serializer.validated_data.get("rejected_reason") or None
        staff.save(
            update_fields=[
                "approval_status",
                "login_enabled",
                "approved_by",
                "approved_at",
                "rejected_reason",
                "updated_at",
            ]
        )
        return self._approval_response(staff, "User rejected successfully")

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, staff_unique_id=None):
        serializer = StaffApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = self.get_object()
        staff.approval_status = Staffcreation.APPROVAL_SUSPENDED
        staff.login_enabled = False
        staff.rejected_reason = serializer.validated_data.get("rejected_reason") or None
        staff.save(
            update_fields=[
                "approval_status",
                "login_enabled",
                "rejected_reason",
                "updated_at",
            ]
        )
        return self._approval_response(staff, "User suspended successfully")

    @action(detail=True, methods=["post"], url_path="reactivate")
    def reactivate(self, request, staff_unique_id=None):
        staff = self.get_object()
        staff.approval_status = Staffcreation.APPROVAL_APPROVED
        staff.login_enabled = True
        staff.approved_by = request.user
        staff.approved_at = timezone.now()
        staff.rejected_reason = None
        staff.failed_login_attempts = 0
        staff.save(
            update_fields=[
                "approval_status",
                "login_enabled",
                "approved_by",
                "approved_at",
                "rejected_reason",
                "failed_login_attempts",
                "updated_at",
            ]
        )
        return self._approval_response(staff, "User reactivated successfully")

    @action(detail=False, methods=["get"], url_path="staff-head-options")
    def staff_head_options(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(active_status=True)

        current_id = request.query_params.get("exclude")
        if current_id:
            queryset = queryset.exclude(staff_unique_id=current_id)

        data = [
            {
                "unique_id": staff.staff_unique_id,
                "employee_name": staff.employee_name,
                "department_id": getattr(staff.department_id, "unique_id", None),
                "department_name": getattr(staff.department_id, "department_name", None),
                "staffusertype_id": getattr(staff.staffusertype_id, "unique_id", None),
                "contractorusertype_id": getattr(staff.contractorusertype_id, "unique_id", None),
            }
            for staff in queryset[:200]
        ]
        return Response(data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            with transaction.atomic():
                instance = serializer.save()

            new_data = self._serialize_instance(instance)

            self.log_audit(
                self.request,
                instance=instance,
                previous_data=None,
                new_data=new_data
            )
            return Response(
                {"status": True, "message": "Staff Created Successfully"},
                status=status.HTTP_201_CREATED
            )

        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=kwargs.pop("partial", False),
        )

        if serializer.is_valid():
            with transaction.atomic():
                previous_data = self._serialize_instance(instance)

            updated_instance = serializer.save()

            new_data = self._serialize_instance(updated_instance)

            self.log_audit(
                self.request,
                instance=updated_instance,
                previous_data=previous_data,
                new_data=new_data
            )
            return Response(
                {"status": True, "message": "Staff Updated Successfully"},
                status=status.HTTP_200_OK
            )

        return Response(
            {"status": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # instance.delete()
        previous_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=None
        )

        instance.delete()

        return Response(
            {"status": True, "message": "Staff Deleted Successfully"},
            status=status.HTTP_200_OK
        )
