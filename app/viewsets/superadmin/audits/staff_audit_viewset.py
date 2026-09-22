from rest_framework import filters
from rest_framework.permissions import IsAuthenticated

from app.models.superadmin.audits.staff_audit import StaffAudit
from app.serializers.superadmin.audits.staff_audit_serializer import StaffAuditSerializer
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.pagination import LimitOffsetWithPage

from rest_framework import viewsets

# StaffAudit's flat geo columns are plain CharFields named without the "_id"
# suffix (state/district/.../panchayat, db_column="..._id") — the helper's
# default field map assumes "..._id"-named fields, which raises FieldError
# against this model's bare names for any requester who actually has a
# StaffDataScope row (the super_admin bypass masks this in casual testing).
FLAT_GEO_FIELD_MAP = {
    "state_id": "state",
    "district_id": "district",
    "area_type_id": "area_type",
    "corporation_id": "corporation",
    "municipality_id": "municipality",
    "town_panchayat_id": "town_panchayat",
    "panchayat_union_id": "panchayat_union",
    "panchayat_id": "panchayat",
}


class StaffAuditViewSet(viewsets.ModelViewSet):
    """Staff-facing audit trail — same events as CommonAudit (see
    app/utils/audit_mixin.py._write_audit_pair, which writes both tables
    together), but the list is restricted to the requester's own local body
    hierarchy. A super admin (is_superuser) still sees every row, matching
    CommonAudit's unscoped behaviour; any other staff user only sees rows
    within their own StaffDataScope subtree, narrowed further by explicit
    ?corporation_id=/?district_id=/etc params.
    """
    throttle_scope = "staff_audit"

    permission_classes = [IsAuthenticated]
    permission_resource = "StaffAudit"

    queryset = StaffAudit.objects.all().order_by("-createdAt")
    serializer_class = StaffAuditSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["module_name", "endpoint_name", "createdBy"]
    ordering_fields = ["createdAt", "module_name"]

    def perform_create(self, serializer):
        serializer.save(createdBy=str(self.request.user))

    def get_queryset(self):
        queryset = super().get_queryset()

        module_name = self.request.query_params.get("module_name")
        method = self.request.query_params.get("method")
        created_by = self.request.query_params.get("createdBy")

        if module_name:
            queryset = queryset.filter(module_name=module_name)

        if method:
            queryset = queryset.filter(method=method)

        if created_by:
            queryset = queryset.filter(createdBy=created_by)

        # filter_flat_geo_queryset_by_params (explicit ?state_id=/etc. params)
        # is intentionally not called here — see the field_map note above;
        # it has no field_map override and would FieldError the same way.
        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset, self.request.user, field_map=FLAT_GEO_FIELD_MAP,
        )

        return queryset
