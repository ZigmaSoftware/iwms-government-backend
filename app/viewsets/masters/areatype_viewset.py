# app/api/views/area_type_view.py

from rest_framework import filters, viewsets
from app.models.masters.areatype import AreaType
from app.serializers.masters.areatype_serializer import AreaTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage


class AreaTypeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    
    serializer_class = AreaTypeSerializer
    lookup_field = "unique_id"
    permission_resource = "AreaType"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name", "state_id__name", "district_id__name"]
    ordering_fields = ["name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="areatype"


    def get_queryset(self):
        queryset = AreaType.objects.filter(is_deleted=False)
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")
        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)
        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        return queryset
    
    def perform_destroy(self, instance):
        instance.delete()
