from django.db.models import Q
from rest_framework import viewsets

from app.models.schedule_masters.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.serializers.schedule_masters.daily_trip_household_collection_serializer import (
    DailyTripHouseholdCollectionSerializer,
)
from app.utils.hierarchy import filter_flat_geo_queryset_by_params, filter_queryset_by_hierarchy


class DailyTripHouseholdCollectionViewSet(viewsets.ModelViewSet):
    serializer_class = DailyTripHouseholdCollectionSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripHouseholdCollection"

    def get_queryset(self):
        queryset = (
            DailyTripHouseholdCollection.objects.select_related(
                "trip_assignment_id",
                "trip_assignment_id__trip_plan_id",
                "customer_id",
                "customer_id__corporation_id",
                "customer_id__municipality_id",
                "customer_id__town_panchayat_id",
                "customer_id__panchayat_union_id",
                "corporation_id",
                "municipality_id",
                "town_panchayat_id",
                "panchayat_union_id",
                "panchayat_id",
                "waste_collection_id",
            )
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        assignment = params.get("trip_assignment_id")
        customer = params.get("customer_id")
        status_value = params.get("status")
        collection_type = params.get("collection_type")
        is_collected = params.get("is_collected")
        trip_date = params.get("date") or params.get("trip_date")
        search = params.get("search")

        if assignment:
            queryset = queryset.filter(trip_assignment_id__unique_id=assignment)
        if customer:
            queryset = queryset.filter(customer_id__unique_id=customer)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if collection_type:
            queryset = queryset.filter(collection_type=collection_type)
        if is_collected is not None:
            queryset = queryset.filter(
                is_collected=str(is_collected).lower() in {"1", "true", "yes"}
            )
        if trip_date:
            queryset = queryset.filter(trip_assignment_id__trip_date=trip_date)
        if search:
            queryset = queryset.filter(
                Q(customer_id__customer_name__icontains=search)
                | Q(trip_assignment_id__unique_id__icontains=search)
            )

        queryset = filter_flat_geo_queryset_by_params(queryset, params)

        return filter_queryset_by_hierarchy(queryset, params)
