from rest_framework import filters
from rest_framework.viewsets import ModelViewSet
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.serializers.masters.hierarchy_serializer import AdministrativeHierarchySerializer
from app.utils.pagination import LimitOffsetWithPage

ADMINISTRATIVE_HIERARCHY_CACHE_SCOPES = ("administrative_hierarchy_list", "administrative_hierarchy_detail")


class AdministrativeHierarchyViewSet(ModelViewSet):
    throttle_scope = "administrative_hierarchy"
    queryset = AdministrativeHierarchy.objects.filter(is_deleted=False)
    serializer_class = AdministrativeHierarchySerializer
    lookup_field = "unique_id"
    permission_resource = "AdministrativeHierarchy"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["level_name", "area_type__name"]
    ordering_fields = ["level_name", "hierarchy_order", "is_active"]

    @cache_api("administrative_hierarchy_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("administrative_hierarchy_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*ADMINISTRATIVE_HIERARCHY_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*ADMINISTRATIVE_HIERARCHY_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*ADMINISTRATIVE_HIERARCHY_CACHE_SCOPES)