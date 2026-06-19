from rest_framework import viewsets
from app.models.masters.city import City
from app.serializers.masters.city_serializer import CitySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets


class CityViewSet(AuditViewSetMixin, viewsets.ModelViewSet):


    queryset = City.objects.filter(is_deleted=False)
    serializer_class = CitySerializer
    lookup_field = "unique_id"

    permission_resource = "City"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="cities"

    def get_queryset(self):
        queryset = City.objects.filter(is_deleted=False)




        district_uid = self.request.query_params.get("district")
        state_uid = self.request.query_params.get("state")
        country_uid = self.request.query_params.get("country")

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        if country_uid:
            queryset = queryset.filter(country_id__unique_id=country_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
