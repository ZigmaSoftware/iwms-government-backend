from rest_framework import viewsets
from app.models.superadmin.common_masters.country import Country
from app.serializers.superadmin.common_masters.country_serializer import CountrySerializer
from app.utils.audit_mixin import AuditViewSetMixin

class CountryViewSet(AuditViewSetMixin,viewsets.ModelViewSet):
    queryset = Country.objects.filter(is_deleted=False)
    serializer_class = CountrySerializer
    lookup_field = "unique_id"

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
