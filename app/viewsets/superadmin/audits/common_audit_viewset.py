from django.db.models import Q
from django.db.models.functions import Replace
from django.db.models import Value
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware
from datetime import datetime, time
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from app.utils.audit_context import resolve_actor, stamp_audit_geo
from app.utils.audit_mixin import get_client_ip
from app.utils.common_audit import CommonAudit
from app.utils.hierarchy import (
    FLAT_GEO_FIELDS,
    LOCAL_BODY_FIELDS,
    STAFF_GEO_LEVEL_FIELDS,
    filter_flat_geo_queryset_by_requester_scope,
)
from app.utils.pagination import LimitOffsetWithPage
from app.serializers.superadmin.audits.common_audit_serializer import (
    CommonAuditSerializer,
    GEO_NAME_ATTRS,
    geo_ref_name,
)

# CommonAudit's flat geo columns are plain CharFields named without the "_id"
# suffix (state/district/.../panchayat, db_column="..._id") — the helper's
# default field map assumes "..._id"-named fields (as most models in this
# codebase have), which raises FieldError against this model's bare names.
# Built from STAFF_GEO_LEVEL_FIELDS so it keeps that most-specific-first
# order: the scope helper stops at the first populated non-local-body level,
# so a state-first map would widen a district-scoped staff to the whole state.
FLAT_GEO_FIELD_MAP = {
    scope_field: scope_field[: -len("_id")] for scope_field in STAFF_GEO_LEVEL_FIELDS
}


class CommonAuditViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Enterprise-wide audit trail.

    Append-only: PATCH/PUT/DELETE are deliberately not routed, since an
    audit log that callers can rewrite or erase is not evidence of
    anything. CREATE stays available for manual events that no viewset
    write hook can observe (Excel template downloads, bulk exports); the
    actor, request context and geo scope on those are resolved
    server-side, never trusted from the payload.
    """

    throttle_scope = "common_audit"

    permission_classes = [IsAuthenticated]

    queryset = CommonAudit.objects.all().order_by("-createdAt")
    serializer_class = CommonAuditSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = [
        "module_name",
        "endpoint_name",
        "createdBy",
        "created_by_name",
        "created_by_id",
        "object_id",
        "reason",
        "ip_address",
    ]
    ordering_fields = ["createdAt", "module_name"]

    def perform_create(self, serializer):
        """
        Stamp actor, request context and geo from the request, so a client
        cannot forge who did it or file the entry under another local body.
        """
        user = self.request.user
        created_by_id, created_by_name, created_by_type = resolve_actor(user)

        # A manual event has no audited record of its own, so a scoped
        # actor's entry is filed under their own geo — keeping it visible to
        # them and to whoever's scope covers them.
        geo = CommonAudit()
        if not getattr(user, "is_superuser", False):
            stamp_audit_geo(geo, user)

        serializer.save(
            createdBy=str(user),
            created_by_id=created_by_id,
            created_by_name=created_by_name,
            created_by_type=created_by_type,
            ip_address=get_client_ip(self.request),
            user_agent=self.request.META.get("HTTP_USER_AGENT"),
            **{field: getattr(geo, field) for field in FLAT_GEO_FIELDS},
        )

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

    def _scoped_base_queryset(self):
        """
        Hierarchy gate. Transaction Audit also serves what used to be the
        separate "Collection Audit" screen — a super_admin sees everything,
        a staff/supervisor with a StaffDataScope row sees only their own
        local body hierarchy, and a staff user with no scope row sees
        nothing (deny-by-default). Enforced here rather than relying on the
        UI to send a geo filter.
        """
        return filter_flat_geo_queryset_by_requester_scope(
            CommonAudit.objects.all().order_by("-createdAt"),
            self.request.user,
            field_map=FLAT_GEO_FIELD_MAP,
        )

    def _filter_by_geo_params(self, queryset, params):
        """
        Explicit ?state_id=/?district_id=/.../?panchayat_id= narrowing, plus
        ?local_body_id= matching any local-body level. Applied on top of the
        scoped base queryset, so a param can only narrow, never widen.
        (The shared filter_flat_geo_queryset_by_params can't be used: it
        filters by "..._id"-suffixed field names, which raises FieldError
        against CommonAudit's bare field names.)
        """
        for param, field in FLAT_GEO_FIELD_MAP.items():
            values = self._getlist(params, param)
            if values:
                queryset = queryset.filter(**{f"{field}__in": values})

        local_body_ids = self._getlist(params, "local_body_id")
        if local_body_ids:
            local_body_query = Q()
            for field in LOCAL_BODY_FIELDS:
                local_body_query |= Q(**{f"{field}__in": local_body_ids})
            queryset = queryset.filter(local_body_query)
        return queryset

    def get_queryset(self):
        queryset = self._scoped_base_queryset()
        params = self.request.query_params

        # module_name/endpoint_name are the audit trail's own field names;
        # main_screen/sub_screen are accepted as aliases since that's how
        # the frontend's nav (Main Screen -> Sub Screen) refers to the same
        # module/endpoint pair everywhere else in the admin UI. Both accept
        # multiple values (multi-select filters on the audit list page).
        module_names = self._getlist(params, "module_name", "main_screen")
        endpoint_names = self._getlist(params, "endpoint_name", "sub_screen")
        method = params.get("method")
        created_by = params.get("createdBy")
        created_by_id = params.get("created_by_id")
        success = params.get("success")

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
            queryset = queryset.filter(method=method.upper())

        if created_by:
            queryset = queryset.filter(createdBy=created_by)

        if created_by_id:
            queryset = queryset.filter(created_by_id=created_by_id)

        # "true"/"false" — isolates rejected writes (validation failures,
        # blocked deletes) from the successful trail.
        if success is not None and success != "":
            queryset = queryset.filter(success=success.lower() in ("1", "true", "yes"))

        # Date range filter on createdAt — date_from is inclusive from
        # 00:00:00, date_to is inclusive through 23:59:59 of that day.
        date_from = params.get("date_from")
        date_to = params.get("date_to")
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
        approval_only = params.get("approval_only")
        if approval_only is not None and approval_only.lower() in ("1", "true", "yes"):
            queryset = queryset.filter(new_data__has_key="approval_status")

        return self._filter_by_geo_params(queryset, params)

    @action(detail=False, methods=["get"], url_path="filter-options")
    def filter_options(self, request):
        """
        Distinct values for the list page's dropdowns, drawn from the same
        scoped queryset so a scoped staff user is never offered another
        local body.
        """
        queryset = self._scoped_base_queryset()

        # The model's Meta.ordering ("-createdAt") is injected into the
        # SELECT by Django, which makes DISTINCT operate on
        # (value, createdAt) pairs and returns the same value once per row.
        # order_by() clears that ordering so DISTINCT applies to the column
        # actually being selected.
        unordered = queryset.order_by()

        def distinct_values(field, source=None):
            rows = (source if source is not None else unordered).values_list(
                field, flat=True
            )
            return sorted({v for v in rows.distinct() if v})

        def named(field, ids):
            return [
                {
                    "unique_id": uid,
                    "name": geo_ref_name(field, uid) or uid,
                    "level": GEO_NAME_ATTRS[field][1],
                }
                for uid in ids
            ]

        def distinct_users():
            rows = (
                unordered.exclude(created_by_id__isnull=True)
                .exclude(created_by_id="")
                .values_list("created_by_id", "created_by_name")
                .distinct()
            )
            # A single id can still appear twice if its denormalized name
            # snapshot changed between writes (e.g. the staff was renamed).
            # Keep the first and dedupe on the id.
            seen, out = set(), []
            for uid, name in rows:
                if uid in seen:
                    continue
                seen.add(uid)
                out.append({"unique_id": uid, "name": name or uid})
            return sorted(out, key=lambda o: (o["name"] or "").lower())

        # Narrow the local body list to the selected district, so picking a
        # district never leaves unrelated local bodies in the next dropdown.
        # Districts/modules/users stay drawn from the unnarrowed set.
        local_body_source = unordered
        district_ids = self._getlist(request.query_params, "district_id")
        if district_ids:
            local_body_source = unordered.filter(district__in=district_ids)

        local_bodies = []
        for field in LOCAL_BODY_FIELDS:
            local_bodies.extend(
                named(field, distinct_values(field, source=local_body_source))
            )

        return Response({
            "districts": sorted(
                named("district", distinct_values("district")),
                key=lambda o: (o["name"] or "").lower(),
            ),
            "local_bodies": sorted(
                local_bodies, key=lambda o: (o["name"] or "").lower()
            ),
            "modules": distinct_values("module_name"),
            "methods": distinct_values("method"),
            "users": distinct_users(),
        })
