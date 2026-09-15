# app/api/views/area_type_view.py

from rest_framework import filters, viewsets
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.utils.cascade_delete import collect_cascade_cache_scopes
from app.models.masters.areatype import AreaType
from app.serializers.masters.areatype_serializer import AreaTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.lite_serializer_mixin import LiteListMixin, make_lite_serializer
from app.utils.pagination import LimitOffsetWithPage

AREA_TYPE_CACHE_SCOPES = ("area_type_list", "area_type_detail")


class AreaTypeViewSet(LiteListMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "area_type"

    serializer_class = AreaTypeSerializer
    # `name` included alongside the aliased `area_type_name` because
    # useGeoHierarchy's edit-hydrate path reads `.name` directly off the
    # cached area-type list (see hydrate() in useGeoHierarchy.ts).
    lite_serializer_class = make_lite_serializer(
        AreaType, "area_type_name", source="name", extra_fields=("name", "state_id", "district_id")
    )
    lookup_field = "unique_id"
    permission_resource = "AreaType"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name", "state_id__name", "district_id__name"]
    ordering_fields = ["name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="areatype"

    SCOPE_FIELD_MAP = {
        "area_type": "unique_id",
        "district": "district_id_id",
        "state": "state_id_id",
    }

    def get_queryset(self):
        queryset = AreaType.objects.filter(is_deleted=False)
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")
        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)
        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset, self.request.user, field_map=self.SCOPE_FIELD_MAP
        )

        return queryset
    
    @cache_api("area_type_list", vary_on_user=True)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("area_type_detail", vary_on_user=True)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*AREA_TYPE_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*AREA_TYPE_CACHE_SCOPES)

    def perform_destroy(self, instance):
        scopes = collect_cascade_cache_scopes(instance)
        super().perform_destroy(instance)
        invalidate_on_commit(*scopes)
