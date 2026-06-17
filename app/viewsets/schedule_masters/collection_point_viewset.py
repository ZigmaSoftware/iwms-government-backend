from rest_framework import viewsets, status
from app.models.schedule_masters.collection_point import Collection_point
from app.serializers.schedule_masters.collection_point_serializer import CollectionPointSerializer
from rest_framework.response import Response
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class CollectionPointViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    serializer_class = CollectionPointSerializer
    lookup_field = "unique_id"

    permission_resource = "CollectionPoint"

    AUDIT_MODULE = "assets"
    AUDIT_ENDPOINT ="collection-point"

    def get_queryset(self):
        queryset = Collection_point.objects.select_related(
            "state_id",
            "district_id",
            "city_id",
            "panchayat_id",
            "ward_id",
            "ward_id__zone_id",
        ).filter(is_deleted=False)

        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        city_uid = self.request.query_params.get("city") or self.request.query_params.get("city_id")
        panchayat_uid = self.request.query_params.get("panchayat") or self.request.query_params.get("panchayat_id")
        ward_uid = self.request.query_params.get("ward") or self.request.query_params.get("ward_id")
        zone_uid = self.request.query_params.get("zone") or self.request.query_params.get("zone_id")



        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)

        if city_uid:
            queryset = queryset.filter(city_id__unique_id=city_uid)

        if panchayat_uid:
            queryset = queryset.filter(panchayat_id__unique_id=panchayat_uid)

        if ward_uid:
            queryset = queryset.filter(ward_id__unique_id=ward_uid)

        if zone_uid:
            queryset = queryset.filter(ward_id__zone_id__unique_id=zone_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
