from rest_framework import filters, viewsets

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.utils.cascade_delete import collect_cascade_cache_scopes
from app.models.masters.ward import Ward
from app.serializers.masters.ward_serializer import LiteWardSerializer, WardSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.lite_serializer_mixin import LiteListMixin
from app.utils.pagination import LimitOffsetWithPage

WARD_CACHE_SCOPES = ("ward_list", "ward_detail")


class WardViewSet(LiteListMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "ward"
    serializer_class = WardSerializer
    lite_serializer_class = LiteWardSerializer
    lookup_field = "unique_id"
    permission_resource = "Ward"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["ward_name"]
    ordering_fields = ["ward_name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "wards"

    def get_queryset(self):
        queryset = Ward.objects.filter(is_deleted=False)
        params = self.request.query_params

        state_uid = params.get("state") or params.get("state_id")
        district_uid = params.get("district") or params.get("district_id")
        area_type_uid = params.get("area_type") or params.get("area_type_id")
        corporation_uid = params.get("corporation") or params.get("corporation_id")
        municipality_uid = params.get("municipality") or params.get("municipality_id")
        town_panchayat_uid = params.get("town_panchayat") or params.get("town_panchayat_id")
        panchayat_union_uid = params.get("panchayat_union") or params.get("panchayat_union_id")
        panchayat_uid = params.get("panchayat") or params.get("panchayat_id")

        if state_uid:
            queryset = queryset.filter(state_id=state_uid)
        if district_uid:
            queryset = queryset.filter(district_id=district_uid)
        if area_type_uid:
            queryset = queryset.filter(area_type_id=area_type_uid)
        if corporation_uid:
            queryset = queryset.filter(corporation_id=corporation_uid)
        if municipality_uid:
            queryset = queryset.filter(municipality_id=municipality_uid)
        if town_panchayat_uid:
            queryset = queryset.filter(town_panchayat_id=town_panchayat_uid)
        if panchayat_union_uid:
            queryset = queryset.filter(panchayat_union_id=panchayat_union_uid)
        if panchayat_uid:
            queryset = queryset.filter(panchayat_id=panchayat_uid)

        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, self.request.user)

        return queryset

    @cache_api("ward_list", vary_on_user=True)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("ward_detail", vary_on_user=True)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*WARD_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*WARD_CACHE_SCOPES)

    def perform_destroy(self, instance):
        scopes = collect_cascade_cache_scopes(instance)
        super().perform_destroy(instance)
        invalidate_on_commit(*scopes)
