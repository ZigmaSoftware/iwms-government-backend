from django.db.models import Q
from rest_framework import filters, viewsets

from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.serializers.core_modules.daily_operations.daily_trip_household_collection_serializer import (
    DailyTripHouseholdCollectionSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_params, filter_queryset_by_hierarchy
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope
from app.utils.pagination import LimitOffsetWithPage


class DailyTripHouseholdCollectionViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "daily_trip_household_collection"
    serializer_class = DailyTripHouseholdCollectionSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripHouseholdCollection"
    # No SearchFilter — get_queryset() already implements its own broader
    # ?search= OR-filter (customer_name/trip_assignment); adding DRF's
    # SearchFilter on top would AND a narrower condition against that and
    # silently drop legitimate matches.
    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["sequence", "status", "collected_at"]

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "daily-trip-household-collection"

    def get_queryset(self):
        queryset = (
            DailyTripHouseholdCollection.objects
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        assignment = params.get("trip_assignment_id")
        customer = params.get("customer_id")
        status_value = params.get("status")
        collection_type = params.get("collection_type")
        is_collected = params.get("is_collected")
        trip_date = params.get("date") or params.get("trip_date")
        ward_id = params.get("ward_id") or params.get("ward_ids")
        search = params.get("search")

        if assignment:
            queryset = queryset.filter(trip_assignment_id=assignment)
        if customer:
            queryset = queryset.filter(customer_id=customer)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if collection_type:
            queryset = queryset.filter(collection_type=collection_type)
        if is_collected is not None:
            queryset = queryset.filter(
                is_collected=str(is_collected).lower() in {"1", "true", "yes"}
            )
        if trip_date:
            from app.models.core_modules.daily_operations.daily_trip_assignment import (
                DailyTripAssignment,
            )

            queryset = queryset.filter(
                trip_assignment_id__in=DailyTripAssignment.objects.filter(
                    trip_date=trip_date, is_deleted=False
                ).values("unique_id")
            )
        if ward_id:
            from app.models.masters.customer_masters.customercreation import (
                CustomerCreation,
            )

            queryset = queryset.filter(
                customer_id__in=CustomerCreation.objects.filter(
                    ward_id=ward_id, is_deleted=False
                ).values("unique_id")
            )
        if search:
            from app.models.masters.customer_masters.customercreation import (
                CustomerCreation as _Customer,
            )

            queryset = queryset.filter(
                Q(customer_id__in=_Customer.objects.filter(
                    customer_name__icontains=search, is_deleted=False
                ).values("unique_id"))
                | Q(trip_assignment_id__icontains=search)
            )

        queryset = filter_flat_geo_queryset_by_params(queryset, params)
        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, self.request.user)

        return filter_queryset_by_hierarchy(queryset, params)
