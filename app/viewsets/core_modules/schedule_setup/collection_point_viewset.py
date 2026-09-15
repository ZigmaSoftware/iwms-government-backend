from rest_framework import filters, viewsets, status
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.serializers.core_modules.schedule_setup.collection_point_serializer import CollectionPointSerializer
from rest_framework.response import Response
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.pagination import LimitOffsetWithPage

# TripPlanSerializer embeds Collection_point details (cp_name, ward names,
# bin names) via get_plan_collection_points, so a collection point write
# must also invalidate cached Trip Plan responses.
COLLECTION_POINT_CACHE_SCOPES = (
    "collection_point_list",
    "collection_point_detail",
    "trip_plan_list",
    "trip_plan_detail",
)


class CollectionPointViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "collection_point"
    serializer_class = CollectionPointSerializer
    lookup_field = "unique_id"

    permission_resource = "CollectionPoint"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["cp_name"]
    ordering_fields = ["cp_name", "collection_type", "is_active"]

    AUDIT_MODULE = "assets"
    AUDIT_ENDPOINT ="collection-point"

    def get_queryset(self):
        queryset = Collection_point.objects.select_related(
            "country",
            "state",
            "district",
            "area_type",
            "corporation",
            "municipality",
            "town_panchayat",
            "panchayat_union",
            "panchayat",
        ).prefetch_related("wards").filter(is_deleted=False)

        for field in (
            "country_id",
            "state_id",
            "district_id",
            "area_type_id",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
        ):
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})

        ward_uid = (
            self.request.query_params.get("ward")
            or self.request.query_params.get("ward_id")
        )
        if ward_uid:
            queryset = queryset.filter(wards__unique_id=ward_uid)

        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, self.request.user)

        return queryset

    @cache_api("collection_point_list", vary_on_user=True)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("collection_point_detail", vary_on_user=True)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*COLLECTION_POINT_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*COLLECTION_POINT_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*COLLECTION_POINT_CACHE_SCOPES)
