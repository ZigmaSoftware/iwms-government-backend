from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
from app.serializers.schedule_masters.trip_plan_collection_point_serializer import (
    TripPlanCollectionPointSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class TripPlanCollectionPointViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = TripPlanCollectionPointSerializer
    lookup_field = "unique_id"
    permission_resource = "TripPlanCollectionPoint"

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "trip-plan-collection-points"

    def get_queryset(self):
        queryset = (
            TripPlanCollectionPoint.objects.select_related(
                "company_id",
                "project_id",
                "trip_plan_id",
                "collection_point_id",
                "zone_id",
                "ward_id",
                "panchayat_id",
                "bin_id",
                "customer_id",
                "customer_id__ward",
                "customer_id__zone",
            )
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        trip_plan = params.get("trip_plan_id")
        company = params.get("company_id")
        project = params.get("project_id")
        collection_point = params.get("collection_point_id")
        zone = params.get("zone_id")
        ward = params.get("ward_id")
        panchayat = params.get("panchayat_id")
        collection_type = params.get("collection_type")

        if trip_plan:
            queryset = queryset.filter(trip_plan_id__unique_id=trip_plan)
        if company:
            queryset = queryset.filter(company_id__unique_id=company)
        if project:
            queryset = queryset.filter(project_id__unique_id=project)
        if collection_point:
            queryset = queryset.filter(collection_point_id__unique_id=collection_point)
        if zone:
            queryset = queryset.filter(zone_id__unique_id=zone)
        if ward:
            queryset = queryset.filter(ward_id__unique_id=ward)
        if panchayat:
            queryset = queryset.filter(panchayat_id__unique_id=panchayat)
        if collection_type:
            queryset = queryset.filter(collection_type=collection_type)

        return queryset
