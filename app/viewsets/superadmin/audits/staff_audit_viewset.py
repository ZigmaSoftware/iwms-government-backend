from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from app.models.superadmin.audits.staff_audit import StaffAudit
from app.serializers.superadmin.audits.staff_audit_serializer import StaffAuditSerializer
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
)

from rest_framework import viewsets


class StaffAuditViewSet(viewsets.ModelViewSet):
    """Staff-facing audit trail — same events as CommonAudit (see
    app/utils/audit_mixin.py._write_audit_pair, which writes both tables
    together), but the list is restricted to the requester's own local body
    hierarchy. A super admin (is_superuser) still sees every row, matching
    CommonAudit's unscoped behaviour; any other staff user only sees rows
    within their own StaffDataScope subtree, narrowed further by explicit
    ?corporation_id=/?district_id=/etc params.
    """

    permission_classes = [IsAuthenticated]
    permission_resource = "StaffAudit"

    queryset = StaffAudit.objects.all().order_by("-createdAt")
    serializer_class = StaffAuditSerializer

    def perform_create(self, serializer):
        serializer.save(createdBy=str(self.request.user))

    def list(self, request, *args, **kwargs):

        queryset = self.get_queryset()

        module_name = request.query_params.get("module_name")
        method = request.query_params.get("method")
        created_by = request.query_params.get("createdBy")

        if module_name:
            queryset = queryset.filter(module_name=module_name)

        if method:
            queryset = queryset.filter(method=method)

        if created_by:
            queryset = queryset.filter(createdBy=created_by)

        queryset = filter_flat_geo_queryset_by_params(queryset, request.query_params)
        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, request.user)

        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
