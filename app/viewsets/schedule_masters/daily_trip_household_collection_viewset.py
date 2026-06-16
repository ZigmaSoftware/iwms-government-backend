from django.db.models import Q

from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.serializers.schedule_masters.daily_trip_household_collection_serializer import (
    DailyTripHouseholdCollectionSerializer,
)
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class DailyTripHouseholdCollectionViewSet(CompanyScopedViewSet):
    serializer_class = DailyTripHouseholdCollectionSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripHouseholdCollection"

    def get_queryset(self):
        queryset = (
            DailyTripHouseholdCollection.objects.select_related(
                "company_id",
                "project_id",
                "trip_assignment_id",
                "trip_assignment_id__trip_plan_id",
                "customer_id",
                "zone_id",
                "ward_id",
                "panchayat_id",
                "waste_collection_id",
            )
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        assignment = params.get("trip_assignment_id")
        customer = params.get("customer_id")
        company = params.get("company_id")
        project = params.get("project_id")
        status_value = params.get("status")
        is_collected = params.get("is_collected")
        trip_date = params.get("date") or params.get("trip_date")
        panchayat = params.get("panchayat_id")
        ward = params.get("ward_id")
        zone = params.get("zone_id")
        search = params.get("search")

        if company:
            queryset = queryset.filter(company_id__unique_id=company)
        if project:
            queryset = queryset.filter(project_id__unique_id=project)
        if assignment:
            queryset = queryset.filter(trip_assignment_id__unique_id=assignment)
        if customer:
            queryset = queryset.filter(customer_id__unique_id=customer)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if is_collected is not None:
            queryset = queryset.filter(
                is_collected=str(is_collected).lower() in {"1", "true", "yes"}
            )
        if trip_date:
            queryset = queryset.filter(trip_assignment_id__trip_date=trip_date)
        if panchayat:
            queryset = queryset.filter(panchayat_id__unique_id=panchayat)
        if ward:
            queryset = queryset.filter(ward_id__unique_id=ward)
        if zone:
            queryset = queryset.filter(zone_id__unique_id=zone)
        if search:
            queryset = queryset.filter(
                Q(customer_id__customer_name__icontains=search)
                | Q(trip_assignment_id__unique_id__icontains=search)
            )

        return queryset
