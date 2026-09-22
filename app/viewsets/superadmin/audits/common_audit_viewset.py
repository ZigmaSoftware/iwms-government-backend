from django.db.models import Q
from django.db.models.functions import Replace
from django.db.models import Value
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware
from datetime import datetime, time
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated

from app.utils.common_audit import CommonAudit
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.pagination import LimitOffsetWithPage
from app.serializers.superadmin.audits.common_audit_serializer import (
    CommonAuditSerializer,
)

from rest_framework import viewsets

# CommonAudit's flat geo columns are plain CharFields named without the "_id"
# suffix (state/district/.../panchayat, db_column="..._id") — the helper's
# default field map assumes "..._id"-named fields (as most models in this
# codebase have), which raises FieldError against this model's bare names.
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

    @staticmethod
    def _getlist(query_params, *names):
        """Collect every value sent under any of `names`, supporting both a
        repeated key (?main_screen=a&main_screen=b, axios's default array
        serialization) and a single comma-separated value, since either can
        reach here depending on the caller."""
        values = []
        for name in names:
            values.extend(query_params.getlist(name))
        expanded = []
        for value in values:
            expanded.extend(part.strip() for part in value.split(",") if part.strip())
        return expanded

    @staticmethod
    def _normalize(value):
        """Strip hyphens/underscores and lowercase, so slugs that only
        differ by separator style (AUDIT_ENDPOINT="areatype" vs UserScreen's
        "area-types") still compare equal."""
        return value.replace("-", "").replace("_", "").lower()

    def get_queryset(self):
        queryset = super().get_queryset()

        # module_name/endpoint_name are the audit trail's own field names;
        # main_screen/sub_screen are accepted as aliases since that's how
        # the frontend's nav (Main Screen -> Sub Screen) refers to the same
        # module/endpoint pair everywhere else in the admin UI. Both accept
        # multiple values (multi-select filters on the audit list page).
        module_names = self._getlist(self.request.query_params, "module_name", "main_screen")
        endpoint_names = self._getlist(self.request.query_params, "endpoint_name", "sub_screen")
        method = self.request.query_params.get("method")
        created_by = self.request.query_params.get("createdBy")
        success = self.request.query_params.get("success")

        # A given viewset's AUDIT_MODULE/AUDIT_ENDPOINT slug (e.g. "areatype")
        # can drift in separator style from the MainScreen/UserScreen name
        # the frontend dropdown sends (e.g. "area-types") without being a
        # different feature. Comparing hyphen/underscore-stripped versions of
        # both sides (via DB-side Replace, so it still works for historical
        # rows without touching every viewset's audit constants) keeps the
        # filter usable despite that drift. Multiple selected values are
        # OR'd together (rows matching any of them).
        if module_names:
            queryset = queryset.annotate(
                _module_name_normalized=Replace(
                    Replace("module_name", Value("-"), Value("")),
                    Value("_"),
                    Value(""),
                )
            )
            module_query = Q()
            for name in module_names:
                module_query |= Q(_module_name_normalized__icontains=self._normalize(name))
            queryset = queryset.filter(module_query)

        if endpoint_names:
            queryset = queryset.annotate(
                _endpoint_name_normalized=Replace(
                    Replace("endpoint_name", Value("-"), Value("")),
                    Value("_"),
                    Value(""),
                )
            )
            endpoint_query = Q()
            for name in endpoint_names:
                endpoint_query |= Q(_endpoint_name_normalized__icontains=self._normalize(name))
            queryset = queryset.filter(endpoint_query)

        if method:
            queryset = queryset.filter(method=method)

        if created_by:
            queryset = queryset.filter(createdBy=created_by)

        if success is not None and success != "":
            queryset = queryset.filter(success=success.lower() in ("1", "true", "yes"))

        # Date range filter on createdAt — date_from is inclusive from
        # 00:00:00, date_to is inclusive through 23:59:59 of that day.
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            parsed = parse_date(date_from)
            if parsed:
                queryset = queryset.filter(
                    createdAt__gte=make_aware(datetime.combine(parsed, time.min))
                )
        if date_to:
            parsed = parse_date(date_to)
            if parsed:
                queryset = queryset.filter(
                    createdAt__lte=make_aware(datetime.combine(parsed, time.max))
                )

        # Approval History is a filtered view over this same audit trail —
        # any row whose captured after-state includes an approval_status
        # key (TripPlan, StaffTemplate, and any future model that reuses the
        # same field name) counts as an approval-relevant event, without
        # hardcoding specific model names here.
        approval_only = self.request.query_params.get("approval_only")
        if approval_only is not None and approval_only.lower() in ("1", "true", "yes"):
            queryset = queryset.filter(new_data__has_key="approval_status")

        # Transaction Audit now also serves what used to be the separate
        # "Collection Audit" screen (StaffAudit) — auto-scope by the
        # requester's own hierarchy the same way StaffAuditViewSet always
        # has: a super_admin sees everything, a staff/supervisor with a
        # StaffDataScope row sees only their own local body, and a staff
        # user with no scope row sees nothing (deny-by-default). Explicit
        # ?state_id=/?district_id=/etc. params narrow further on top.
        # NOTE: filter_flat_geo_queryset_by_params (explicit ?state_id=/etc.
        # params) is intentionally NOT called here — it has no field_map
        # override and filters by "..._id"-suffixed field names directly,
        # which raises FieldError against CommonAudit/StaffAudit's bare
        # field names (state/district/... not state_id/district_id/...).
        # Nothing in the frontend currently sends those params to this
        # endpoint, so skipping it only omits an unused manual-narrowing
        # feature, not the auto-scoping this change is actually for.
        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset, self.request.user, field_map=FLAT_GEO_FIELD_MAP,
        )

        return queryset
