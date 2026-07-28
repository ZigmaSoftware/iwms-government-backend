from rest_framework import filters
from rest_framework.permissions import IsAuthenticated

from app.utils.common_audit import CommonAudit
from app.utils.pagination import LimitOffsetWithPage
from app.serializers.superadmin.audits.common_audit_serializer import (
    CommonAuditSerializer,
)

from rest_framework import viewsets


class CommonAuditViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]

    queryset = CommonAudit.objects.all().order_by("-createdAt")
    serializer_class = CommonAuditSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["module_name", "endpoint_name", "createdBy"]
    ordering_fields = ["createdAt", "module_name"]

    def perform_create(self, serializer):
        serializer.save(createdBy=str(self.request.user))

    def get_queryset(self):
        queryset = super().get_queryset()

        # Optional filters
        module_name = self.request.query_params.get("module_name")
        method = self.request.query_params.get("method")
        created_by = self.request.query_params.get("createdBy")

        if module_name:
            queryset = queryset.filter(module_name=module_name)

        if method:
            queryset = queryset.filter(method=method)

        if created_by:
            queryset = queryset.filter(createdBy=created_by)

        return queryset
