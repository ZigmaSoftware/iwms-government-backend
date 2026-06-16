from rest_framework import filters

from app.models.masters.designation import Designation
from app.serializers.masters.designation_serializer import DesignationSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class DesignationViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    queryset = Designation.objects.filter(is_deleted=False)
    serializer_class = DesignationSerializer
    lookup_field = "unique_id"
    permission_resource = "Designation"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["designation_name", "designation_group", "description"]
    ordering_fields = ["designation_name", "designation_group", "created_at"]
    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "designations"

    def get_queryset(self):
        queryset = Designation.objects.filter(is_deleted=False)
        status_value = self.request.query_params.get("status")
        group = self.request.query_params.get("designation_group")
        department_id = self.request.query_params.get("department_id")
        if status_value in {"active", "inactive"}:
            queryset = queryset.filter(is_active=status_value == "active")
        if group:
            queryset = queryset.filter(designation_group__iexact=group)
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        return queryset
