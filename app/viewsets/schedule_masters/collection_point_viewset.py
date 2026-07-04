from rest_framework import viewsets, status
from app.models.schedule_masters.collection_point import Collection_point
from app.serializers.schedule_masters.collection_point_serializer import CollectionPointSerializer
from rest_framework.response import Response
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets
from app.utils.hierarchy import filter_queryset_by_hierarchy


class CollectionPointViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CollectionPointSerializer
    lookup_field = "unique_id"

    permission_resource = "CollectionPoint"

    AUDIT_MODULE = "assets"
    AUDIT_ENDPOINT ="collection-point"

    def get_queryset(self):
        queryset = Collection_point.objects.select_related(
            "location_node",
            "location_node__level",
        ).filter(is_deleted=False)

        queryset = filter_queryset_by_hierarchy(queryset, self.request.query_params)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
