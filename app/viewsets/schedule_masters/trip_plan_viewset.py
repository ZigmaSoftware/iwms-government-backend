from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.trip_plan import TripPlan
from app.serializers.schedule_masters.trip_plan_serializer import (
    TripPlanSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_queryset_by_hierarchy


class TripPlanViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = TripPlan.objects.select_related(
        "district_id",
        "corporation_id",
        "municipality_id",
        "town_panchayat_id",
        "panchayat_union_id",
        "panchayat_id",
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
        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)
        return filter_queryset_by_hierarchy(queryset, self.request.query_params)

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
