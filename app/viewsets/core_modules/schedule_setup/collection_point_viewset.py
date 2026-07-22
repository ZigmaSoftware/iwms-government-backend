from rest_framework import viewsets, status
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.serializers.core_modules.schedule_setup.collection_point_serializer import CollectionPointSerializer
from rest_framework.response import Response
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope


class CollectionPointViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CollectionPointSerializer
    lookup_field = "unique_id"

    permission_resource = "CollectionPoint"

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
        ).filter(is_deleted=False)

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

        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, self.request.user)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
