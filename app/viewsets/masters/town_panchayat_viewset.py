from app.models.masters.town_panchayat import TownPanchayat
from app.serializers.masters.town_panchayat_serializer import TownPanchayatSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from rest_framework import filters, viewsets
from app.utils.pagination import LimitOffsetWithPage


class TownPanchayatViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TownPanchayatSerializer
    lookup_field = "unique_id"
    permission_resource = "TownPanchayat"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["town_panchayat_name", "state_id__name", "district_id__name", "area_type_id__name"]
    ordering_fields = ["town_panchayat_name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "town-panchayats"

    SCOPE_FIELD_MAP = {
        "town_panchayat": "unique_id",
        "district": "district_id_id",
        "state": "state_id_id",
    }

    def get_queryset(self):
        queryset = TownPanchayat.objects.filter(is_deleted=False)

        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")
        area_type_uid = self.request.query_params.get("area_type") or self.request.query_params.get("area_type_id")

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)
        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)
        if area_type_uid:
            queryset = queryset.filter(area_type_id__unique_id=area_type_uid)

        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset, self.request.user, field_map=self.SCOPE_FIELD_MAP
        )

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
