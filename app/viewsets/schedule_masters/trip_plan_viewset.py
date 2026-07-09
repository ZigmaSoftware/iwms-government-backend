from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.trip_plan import TripPlan
from app.serializers.schedule_masters.trip_plan_serializer import (
    TripPlanSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_requester_scope


class TripPlanViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = TripPlan.objects.select_related(
        "state",
        "district",
        "area_type",
        "corporation",
        "municipality",
        "town_panchayat",
        "panchayat_union",
        "panchayat",
        "staff_template_id",
        "staff_template_id__driver_id",
        "staff_template_id__operator_id",
        "vehicle_id",
        "supervisor_id",
        "property_id",
        "sub_property_id",
        "waste_type_id",
    ).prefetch_related("plan_collection_points", "waste_types").filter(is_deleted=False)

    serializer_class = TripPlanSerializer
    lookup_field = "unique_id"
    swagger_tags = ["Desktop / Operations / Trip Plan"]
    permission_resource = "TripPlan"
    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "trip-plans"

    def get_queryset(self):
        queryset = super().get_queryset()

        params = self.request.query_params
        for field in ("state_id", "district_id", "area_type_id", "corporation_id", "municipality_id", "town_panchayat_id", "panchayat_union_id", "panchayat_id"):
            value = params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})

        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, self.request.user)
        return queryset

    @swagger_auto_schema(request_body=TripPlanSerializer)
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @swagger_auto_schema(request_body=TripPlanSerializer)
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.daily_trip_assignments.filter(is_deleted=False).exists():
            return Response(
                {"detail": "Trip plans with daily assignments cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)
