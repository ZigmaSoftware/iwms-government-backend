from rest_framework import filters, viewsets

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.utils.cascade_delete import collect_cascade_cache_scopes
from app.models.superadmin.common_masters.state import State
from app.serializers.superadmin.common_masters.state_serializer import StateSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.lite_serializer_mixin import LiteListMixin, make_lite_serializer
from app.utils.pagination import LimitOffsetWithPage

STATE_CACHE_SCOPES = ("state_list", "state_detail")


class StateViewSet(LiteListMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "state"
    queryset = State.objects.all()   # REQUIRED for DRF basename detection
    serializer_class = StateSerializer
    # `name` included alongside the aliased `state_name` because
    # useGeoHierarchy's resolveName() reads `.name` first (see useGeoHierarchy.ts).
    lite_serializer_class = make_lite_serializer(State, "state_name", source="name", extra_fields=("name",))
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name", "label"]
    ordering_fields = ["name", "label", "is_active"]

    permission_resource = "State"

    AUDIT_MODULE = "common-masters"
    AUDIT_ENDPOINT = "states"

    SCOPE_FIELD_MAP = {
        "state": "unique_id",
    }

    def get_queryset(self):
        queryset = State.objects.filter(is_deleted=False)\
            .select_related("country_id", "continent_id")\
            .order_by("name")

        country_uid = self.request.query_params.get("country")
        if country_uid:
            queryset = queryset.filter(
                country_id__unique_id=country_uid
            )

        continent_uid = self.request.query_params.get("continent")
        if continent_uid:
            queryset = queryset.filter(
                continent_id__unique_id=continent_uid
            )

        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset, self.request.user, field_map=self.SCOPE_FIELD_MAP
        )

        return queryset

    # vary_on_user stays True (the default) here: get_queryset() filters by
    # the requester's own geo scope (filter_flat_geo_queryset_by_requester_scope
    # above), so two different users can legitimately see different State
    # lists — the cache key must not be shared across them.
    @cache_api("state_list")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("state_detail")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*STATE_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*STATE_CACHE_SCOPES)

    def perform_destroy(self, instance):
        scopes = collect_cascade_cache_scopes(instance)
        super().perform_destroy(instance)
        invalidate_on_commit(*scopes)
