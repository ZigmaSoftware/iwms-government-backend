from rest_framework import filters, viewsets
from app.models.superadmin.common_masters.continent import Continent
from app.serializers.superadmin.common_masters.continent_serializer import ContinentSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

class ContinentViewSet(AuditViewSetMixin,viewsets.ModelViewSet):
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

    def perform_destroy(self, instance):
        instance.delete()
