from rest_framework import filters, viewsets
from app.models.superadmin.common_masters.country import Country
from app.serializers.superadmin.common_masters.country_serializer import CountrySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

class CountryViewSet(AuditViewSetMixin,viewsets.ModelViewSet):
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

    def perform_destroy(self, instance):
        instance.delete()  # Soft delete
