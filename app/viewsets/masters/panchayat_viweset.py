from rest_framework import viewsets, status
from app.models.masters.panchayat import Panchayat
from app.serializers.masters.panchayat_serializer import PanchayatSerializer
from rest_framework.response import Response
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets


class PanhayatViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = PanchayatSerializer
    lookup_field = "unique_id"
    permission_resource = "Panchayat"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="panchayat"

    def get_queryset(self):
        queryset = Panchayat.objects.filter(is_deleted=False)




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
