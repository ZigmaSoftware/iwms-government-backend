from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from app.utils.common_audit import CommonAudit
from app.serializers.superadmin.audits.common_audit_serializer import (
    CommonAuditSerializer,
)

from rest_framework import viewsets


class CommonAuditViewSet(viewsets.ModelViewSet):

    permission_classes = [IsAuthenticated]

    queryset = CommonAudit.objects.all().order_by("-createdAt")
    serializer_class = CommonAuditSerializer

    def perform_create(self, serializer):
        serializer.save(createdBy=str(self.request.user))

    def list(self, request, *args, **kwargs):

        queryset = self.get_queryset()

        # Optional filters
        module_name = request.query_params.get("module_name")
        method = request.query_params.get("method")
        created_by = request.query_params.get("createdBy")

        if module_name:
            queryset = queryset.filter(module_name=module_name)

        if method:
            queryset = queryset.filter(method=method)

        if created_by:
            queryset = queryset.filter(createdBy=created_by)

        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
