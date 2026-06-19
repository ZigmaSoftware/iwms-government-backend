from rest_framework import filters, viewsets, status
from app.models.masters.panchayat import Panchayat
from app.serializers.masters.panchayat_serializer import PanchayatSerializer
from rest_framework.response import Response
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage


class PanhayatViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = PanchayatSerializer
    lookup_field = "unique_id"
    permission_resource = "Panchayat"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["panchayat_name", "state_id__name", "district_id__name", "area_type_id__name"]
    ordering_fields = ["panchayat_name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="panchayat"

    def get_queryset(self):
        queryset = Panchayat.objects.filter(is_deleted=False)




        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")
        area_type_uid = self.request.query_params.get("area_type") or self.request.query_params.get("area_type_id")

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)
        if area_type_uid:
            queryset = queryset.filter(area_type_id__unique_id=area_type_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
