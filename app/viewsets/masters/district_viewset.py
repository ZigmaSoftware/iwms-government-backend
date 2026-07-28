from rest_framework import filters, viewsets
from app.models.masters.district import District
from app.serializers.masters.district_serializer import DistrictSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.lite_serializer_mixin import LiteListMixin, make_lite_serializer
from app.utils.pagination import LimitOffsetWithPage

class DistrictViewSet(LiteListMixin, AuditViewSetMixin, viewsets.ModelViewSet):

    queryset = District.objects.filter(is_deleted=False)
    serializer_class = DistrictSerializer
    # `name` included alongside the aliased `district_name` because
    # useGeoHierarchy's resolveName() reads `.name` first (see useGeoHierarchy.ts).
    lite_serializer_class = make_lite_serializer(
        District, "district_name", source="name", extra_fields=("name", "state_id")
    )
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name", "district_code", "state_id__name"]
    ordering_fields = ["name", "district_code", "is_active"]
    permission_resource = "District"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="districts"

    SCOPE_FIELD_MAP = {
        "district": "unique_id",
        "state": "state_id_id",
    }

    def get_queryset(self):
        queryset = District.objects.filter(is_deleted=False)




        country_uid = self.request.query_params.get("country")
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")
        continent_uid = self.request.query_params.get("continent")

        if country_uid:
            queryset = queryset.filter(country_id__unique_id=country_uid)

        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        if continent_uid:
            queryset = queryset.filter(continent_id__unique_id=continent_uid)

        queryset = filter_flat_geo_queryset_by_requester_scope(
            queryset, self.request.user, field_map=self.SCOPE_FIELD_MAP
        )

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
