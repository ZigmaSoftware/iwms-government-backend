from rest_framework import filters, viewsets
from app.models.superadmin.common_masters.state import State
from app.serializers.superadmin.common_masters.state_serializer import StateSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.pagination import LimitOffsetWithPage


class StateViewSet(AuditViewSetMixin,viewsets.ModelViewSet):
    queryset = State.objects.all()   # REQUIRED for DRF basename detection
    serializer_class = StateSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name", "label"]
    ordering_fields = ["name", "label", "is_active"]

    permission_resource = "State"

    AUDIT_MODULE = "common-masters"
    AUDIT_ENDPOINT = "states"

    SCOPE_FIELD_MAP = {
        "state": "unique_id",
    }

    def get_queryset(self):
        queryset = State.objects.filter(is_deleted=False)\
            .select_related("country_id", "continent_id")\
            .order_by("name")

        country_uid = self.request.query_params.get("country")
        if country_uid:
            queryset = queryset.filter(
                country_id__unique_id=country_uid
            )

        continent_uid = self.request.query_params.get("continent")
        if continent_uid:
            queryset = queryset.filter(
                continent_id__unique_id=continent_uid
            )

        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset, self.request.user, field_map=self.SCOPE_FIELD_MAP
        )

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
