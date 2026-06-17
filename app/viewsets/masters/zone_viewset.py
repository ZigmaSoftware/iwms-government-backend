from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.masters.zone import Zone
from app.serializers.masters.zone_serializer import ZoneSerializer

from rest_framework.viewsets import ModelViewSet
from app.models.masters.zone import Zone
from app.serializers.masters.zone_serializer import ZoneSerializer
from app.utils.audit_mixin import AuditViewSetMixin


class ZoneViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    queryset = Zone.objects.filter(is_deleted=False)
    serializer_class = ZoneSerializer
    lookup_field = "unique_id"

    permission_resource = "Zone"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="zone"


    def get_queryset(self):
        queryset = Zone.objects.filter(is_deleted=False)




        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        city_uid = self.request.query_params.get("city") or self.request.query_params.get("city_id")
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if city_uid:
            queryset = queryset.filter(city_id__unique_id=city_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
