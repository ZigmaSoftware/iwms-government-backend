from rest_framework import filters, viewsets

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.utils.cascade_delete import collect_cascade_cache_scopes
from app.models.masters.corporation import Corporation
from app.serializers.masters.corporation_serializer import CorporationSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.lite_serializer_mixin import LiteListMixin, make_lite_serializer
from app.utils.pagination import LimitOffsetWithPage

CORPORATION_CACHE_SCOPES = ("corporation_list", "corporation_detail")


class CorporationViewSet(LiteListMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "corporation"
    serializer_class = CorporationSerializer
    lite_serializer_class = make_lite_serializer(
        Corporation, "corporation_name", extra_fields=("state_id", "district_id", "area_type_id")
    )
    lookup_field = "unique_id"
    permission_resource = "Corporation"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["corporation_name"]
    ordering_fields = ["corporation_name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "corporations"

    SCOPE_FIELD_MAP = {
        "corporation_id": "unique_id",
        "district": "district_id",
        "state": "state_id",
    }

    def get_queryset(self):
        queryset = Corporation.objects.filter(is_deleted=False)
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")
        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        area_type_uid = self.request.query_params.get("area_type") or self.request.query_params.get("area_type_id")

        if state_uid:
            queryset = queryset.filter(state_id=state_uid)
        if district_uid:
            queryset = queryset.filter(district_id=district_uid)
        if area_type_uid:
            queryset = queryset.filter(area_type_id=area_type_uid)

        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset, self.request.user, field_map=self.SCOPE_FIELD_MAP
        )

        return queryset

    @cache_api("corporation_list", vary_on_user=True)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("corporation_detail", vary_on_user=True)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*CORPORATION_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*CORPORATION_CACHE_SCOPES)

    def perform_destroy(self, instance):
        scopes = collect_cascade_cache_scopes(instance)
        super().perform_destroy(instance)
        invalidate_on_commit(*scopes)
