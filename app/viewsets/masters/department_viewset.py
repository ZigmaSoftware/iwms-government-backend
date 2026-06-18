from rest_framework import filters

from app.models.masters.department import Department
from app.serializers.masters.department_serializer import DepartmentSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets


class DepartmentViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = Department.objects.filter(is_deleted=False)
    serializer_class = DepartmentSerializer
    lookup_field = "unique_id"
    permission_resource = "Department"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["department_name", "department_code", "description"]
    ordering_fields = ["department_name", "department_code", "created_at"]
    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "departments"

    def get_queryset(self):
        queryset = Department.objects.filter(is_deleted=False)
        status_value = self.request.query_params.get("status")
        if status_value in {"active", "inactive"}:
            queryset = queryset.filter(is_active=status_value == "active")
        return queryset
