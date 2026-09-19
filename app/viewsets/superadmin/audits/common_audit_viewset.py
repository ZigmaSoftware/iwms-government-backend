from rest_framework import filters
from rest_framework.permissions import IsAuthenticated

from app.utils.common_audit import CommonAudit
from app.utils.pagination import LimitOffsetWithPage
from app.serializers.superadmin.audits.common_audit_serializer import (
    CommonAuditSerializer,
)

from rest_framework import viewsets


class CommonAuditViewSet(viewsets.ModelViewSet):
    throttle_scope = "common_audit"

    permission_classes = [IsAuthenticated]

    queryset = CommonAudit.objects.all().order_by("-createdAt")
    serializer_class = CommonAuditSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["module_name", "endpoint_name", "createdBy", "reason"]
    ordering_fields = ["createdAt", "module_name"]

    def perform_create(self, serializer):
        serializer.save(createdBy=str(self.request.user))

    def get_queryset(self):
        queryset = super().get_queryset()

        # module_name/endpoint_name are the audit trail's own field names;
        # main_screen/sub_screen are accepted as aliases since that's how
        # the frontend's nav (Main Screen -> Sub Screen) refers to the same
        # module/endpoint pair everywhere else in the admin UI.
        module_name = (
            self.request.query_params.get("module_name")
            or self.request.query_params.get("main_screen")
        )
        endpoint_name = (
            self.request.query_params.get("endpoint_name")
            or self.request.query_params.get("sub_screen")
        )
        method = self.request.query_params.get("method")
        created_by = self.request.query_params.get("createdBy")
        success = self.request.query_params.get("success")

        # icontains rather than an exact match: MainScreen/UserScreen names
        # (e.g. "main-screens" from the UserScreen list, sent verbatim by
        # the frontend dropdown) can drift slightly from the slug a given
        # viewset actually stamped on AUDIT_MODULE/AUDIT_ENDPOINT (e.g.
        # "main-screen"), so a loose match keeps the filter usable without
        # having to keep every viewset's audit constants byte-identical to
        # the screen-management records.
        if module_name:
            queryset = queryset.filter(module_name__icontains=module_name)

        if endpoint_name:
            queryset = queryset.filter(endpoint_name__icontains=endpoint_name)

        if method:
            queryset = queryset.filter(method=method)

        if created_by:
            queryset = queryset.filter(createdBy=created_by)

        if success is not None and success != "":
            queryset = queryset.filter(success=success.lower() in ("1", "true", "yes"))

        return queryset
