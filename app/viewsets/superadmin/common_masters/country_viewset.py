from rest_framework import filters, viewsets
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.utils.cascade_delete import collect_cascade_cache_scopes
from app.models.superadmin.common_masters.country import Country
from app.serializers.superadmin.common_masters.country_serializer import CountrySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

COUNTRY_CACHE_SCOPES = ("country_list", "country_detail")


class CountryViewSet(AuditViewSetMixin,viewsets.ModelViewSet):
    throttle_scope = "country"
    queryset = Country.objects.filter(is_deleted=False)
    serializer_class = CountrySerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name", "continent_id__name"]
    ordering_fields = ["name", "is_active"]

    AUDIT_MODULE = "common-masters"
    AUDIT_ENDPOINT = "countries"

    def get_queryset(self):
        queryset = Country.objects.filter(is_deleted=False)

        # Filter by Continent Unique ID
        continent_uid = self.request.query_params.get("continent")
        if continent_uid:
            queryset = queryset.filter(
                continent_id__unique_id=continent_uid
            )
            
        return queryset

    @cache_api("country_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("country_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*COUNTRY_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*COUNTRY_CACHE_SCOPES)

    def perform_destroy(self, instance):
        scopes = collect_cascade_cache_scopes(instance)
        super().perform_destroy(instance)
        invalidate_on_commit(*scopes)
