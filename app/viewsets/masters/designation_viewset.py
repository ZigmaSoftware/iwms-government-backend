from rest_framework import filters

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.masters.designation import Designation
from app.serializers.masters.designation_serializer import DesignationSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from rest_framework import viewsets

DESIGNATION_CACHE_SCOPES = ("designation_list", "designation_detail")


class DesignationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "designation"
    queryset = Designation.objects.filter(is_deleted=False)
    serializer_class = DesignationSerializer
    lookup_field = "unique_id"
    permission_resource = "Designation"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
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

    @cache_api("designation_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("designation_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*DESIGNATION_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*DESIGNATION_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*DESIGNATION_CACHE_SCOPES)
