from rest_framework import filters

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.masters.department import Department
from app.serializers.masters.department_serializer import DepartmentSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from rest_framework import viewsets

DEPARTMENT_CACHE_SCOPES = ("department_list", "department_detail")


class DepartmentViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "department"
    queryset = Department.objects.filter(is_deleted=False)
    serializer_class = DepartmentSerializer
    lookup_field = "unique_id"
    permission_resource = "Department"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["department_name", "department_code", "description"]
    ordering_fields = ["department_name", "department_code", "created_at"]
    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "departments"

    def get_queryset(self):
        queryset = Department.objects.filter(is_deleted=False)
        status_value = self.request.query_params.get("status")
        if status_value in {"active", "inactive"}:
            queryset = queryset.filter(is_active=status_value == "active")
        corporation_id = self.request.query_params.get("corporation_id")
        if corporation_id:
            queryset = queryset.filter(corporation_id=corporation_id)
        return queryset

    @cache_api("department_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("department_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*DEPARTMENT_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*DEPARTMENT_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*DEPARTMENT_CACHE_SCOPES)
