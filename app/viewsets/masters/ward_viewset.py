from rest_framework import filters, viewsets

from app.models.masters.ward import Ward
from app.serializers.masters.ward_serializer import WardSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.pagination import LimitOffsetWithPage


class WardViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = WardSerializer
    lookup_field = "unique_id"
    permission_resource = "Ward"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = [
        "ward_name",
        "state__name",
        "district__name",
        "area_type__name",
        "corporation__corporation_name",
        "municipality__municipality_name",
        "town_panchayat__town_panchayat_name",
        "panchayat_union__union_name",
        "panchayat__panchayat_name",
    ]
    ordering_fields = ["ward_name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "wards"

    def get_queryset(self):
        queryset = Ward.objects.filter(is_deleted=False)
        params = self.request.query_params

        state_uid = params.get("state") or params.get("state_id")
        district_uid = params.get("district") or params.get("district_id")
        area_type_uid = params.get("area_type") or params.get("area_type_id")
        corporation_uid = params.get("corporation") or params.get("corporation_id")
        municipality_uid = params.get("municipality") or params.get("municipality_id")
        town_panchayat_uid = params.get("town_panchayat") or params.get("town_panchayat_id")
        panchayat_union_uid = params.get("panchayat_union") or params.get("panchayat_union_id")
        panchayat_uid = params.get("panchayat") or params.get("panchayat_id")

        if state_uid:
            queryset = queryset.filter(state__unique_id=state_uid)
        if district_uid:
            queryset = queryset.filter(district__unique_id=district_uid)
        if area_type_uid:
            queryset = queryset.filter(area_type__unique_id=area_type_uid)
        if corporation_uid:
            queryset = queryset.filter(corporation__unique_id=corporation_uid)
        if municipality_uid:
            queryset = queryset.filter(municipality__unique_id=municipality_uid)
        if town_panchayat_uid:
            queryset = queryset.filter(town_panchayat__unique_id=town_panchayat_uid)
        if panchayat_union_uid:
            queryset = queryset.filter(panchayat_union__unique_id=panchayat_union_uid)
        if panchayat_uid:
            queryset = queryset.filter(panchayat__unique_id=panchayat_uid)

        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, self.request.user)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
