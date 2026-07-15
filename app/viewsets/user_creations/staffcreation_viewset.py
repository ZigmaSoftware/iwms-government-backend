from django.db import transaction

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.user_creations.staffcreation_serializer import StaffcreationSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_staff_queryset_by_requester_scope
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
        "department",
        "designation",
        "department_id__department_name",
        "department_id__department_code",
        "designation_id__designation_name",
        "designation_id__designation_group",
    ]
    ordering_fields = ["staff_unique_id", "employee_name", "created_at"]

    def get_queryset(self):
        queryset = Staffcreation.objects.select_related(
            "personal_details",
            "department_id",
            "designation_id",
            "staffusertype_id",
            "contractorusertype_id",
        )

        employee_name = self.request.query_params.get("employee_name", None)
        active_status = self.request.query_params.get("active_status", None)
        department_id = self.request.query_params.get("department_id", None)
        staffusertype_id = self.request.query_params.get("staffusertype_id", None)
        contractorusertype_id = self.request.query_params.get("contractorusertype_id", None)
        login_enabled = self.request.query_params.get("login_enabled", None)
        state_id = self.request.query_params.get("state_id", None)
        district_id = self.request.query_params.get("district_id", None)
        area_type_id = self.request.query_params.get("area_type_id", None)
        corporation_id = self.request.query_params.get("corporation_id", None)
        municipality_id = self.request.query_params.get("municipality_id", None)
        town_panchayat_id = self.request.query_params.get("town_panchayat_id", None)
        panchayat_union_id = self.request.query_params.get("panchayat_union_id", None)
        panchayat_id = self.request.query_params.get("panchayat_id", None)

        if employee_name:
            queryset = queryset.filter(employee_name__icontains=employee_name)

        if active_status in ["0", "1"]:
            queryset = queryset.filter(active_status=active_status == "1")

        if department_id:
            queryset = queryset.filter(department_id__unique_id=department_id)

        if staffusertype_id:
            queryset = queryset.filter(staffusertype_id__unique_id=staffusertype_id)

        if contractorusertype_id:
            queryset = queryset.filter(contractorusertype_id__unique_id=contractorusertype_id)

        if login_enabled in ["0", "1", "true", "false", "True", "False"]:
            queryset = queryset.filter(login_enabled=str(login_enabled).lower() in ["1", "true"])

        if state_id:
            queryset = queryset.filter(state_id=state_id)
        if district_id:
            queryset = queryset.filter(district_id=district_id)
        if area_type_id:
            queryset = queryset.filter(area_type_id=area_type_id)
        if corporation_id:
            queryset = queryset.filter(corporation_id=corporation_id)
        if municipality_id:
            queryset = queryset.filter(municipality_id=municipality_id)
        if town_panchayat_id:
            queryset = queryset.filter(town_panchayat_id=town_panchayat_id)
        if panchayat_union_id:
            queryset = queryset.filter(panchayat_union_id=panchayat_union_id)
        if panchayat_id:
            queryset = queryset.filter(panchayat_id=panchayat_id)

        # A District-level (etc.) staff member automatically sees every staff
        # record scoped at or beneath their own geo scope (e.g. every
        # Corporation/Municipality/Town Panchayat/Panchayat Union/Panchayat
        # under their District). ?state_id=/?district_id=/etc. let a broader
        # user (e.g. State/super admin) drill into one specific area.
        queryset = filter_staff_queryset_by_requester_scope(queryset, self.request.user)

        return queryset.order_by("-created_at")

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
