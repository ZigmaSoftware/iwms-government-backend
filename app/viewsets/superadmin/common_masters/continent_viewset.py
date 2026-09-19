from rest_framework import filters, viewsets
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.superadmin.common_masters.continent import Continent
from app.serializers.superadmin.common_masters.continent_serializer import ContinentSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.cascade_delete import collect_cascade_cache_scopes
from app.utils.pagination import LimitOffsetWithPage

CONTINENT_CACHE_SCOPES = ("continent_list", "continent_detail")


class ContinentViewSet(AuditViewSetMixin,viewsets.ModelViewSet):
    throttle_scope = "continent"
    queryset = Continent.objects.filter(is_deleted=False)
    serializer_class = ContinentSerializer
    lookup_field = "unique_id"
    permission_resource = "Continent"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name"]
    ordering_fields = ["name", "is_active"]

    AUDIT_MODULE = "common-masters"
    AUDIT_ENDPOINT = "continents"

    @cache_api("continent_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("continent_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*CONTINENT_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*CONTINENT_CACHE_SCOPES)

    def perform_destroy(self, instance):
        scopes = collect_cascade_cache_scopes(instance)
        super().perform_destroy(instance)
        invalidate_on_commit(*scopes)
