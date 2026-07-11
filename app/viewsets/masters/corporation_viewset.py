from rest_framework import filters, viewsets

from app.models.masters.corporation import Corporation
from app.serializers.masters.corporation_serializer import CorporationSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.pagination import LimitOffsetWithPage


class CorporationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CorporationSerializer
    lookup_field = "unique_id"
    permission_resource = "Corporation"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["corporation_name", "state_id__name", "district_id__name", "area_type_id__name"]
    ordering_fields = ["corporation_name", "is_active"]

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "corporations"

    SCOPE_FIELD_MAP = {
        "corporation": "unique_id",
        "district": "district_id_id",
        "state": "state_id_id",
    }

    def get_queryset(self):
        queryset = Corporation.objects.filter(is_deleted=False)
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")
        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        area_type_uid = self.request.query_params.get("area_type") or self.request.query_params.get("area_type_id")

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)
        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)
        if area_type_uid:
            queryset = queryset.filter(area_type_id__unique_id=area_type_uid)

        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset, self.request.user, field_map=self.SCOPE_FIELD_MAP
        )

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
