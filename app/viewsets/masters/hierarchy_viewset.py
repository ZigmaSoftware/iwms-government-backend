from rest_framework import filters
from rest_framework.viewsets import ModelViewSet
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.serializers.masters.hierarchy_serializer import AdministrativeHierarchySerializer
from app.utils.pagination import LimitOffsetWithPage


class AdministrativeHierarchyViewSet(ModelViewSet):
    queryset = AdministrativeHierarchy.objects.filter(is_deleted=False)
    serializer_class = AdministrativeHierarchySerializer
    lookup_field = "unique_id"
    permission_resource = "AdministrativeHierarchy"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["level_name", "area_type__name"]
    ordering_fields = ["level_name", "hierarchy_order", "is_active"]