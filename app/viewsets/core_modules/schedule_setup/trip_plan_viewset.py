from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.serializers.core_modules.schedule_setup.trip_plan_serializer import (
    TripPlanSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
)
from app.utils.pagination import LimitOffsetWithPage
from app.utils.plain_ref_search import PlainRefSearchFilter

TRIP_PLAN_CACHE_SCOPES = ("trip_plan_list", "trip_plan_detail")


class TripPlanViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "trip_plan"
    queryset = TripPlan.objects.filter(is_deleted=False)

    serializer_class = TripPlanSerializer
    lookup_field = "unique_id"
    swagger_tags = ["Desktop / Operations / Trip Plan"]
    permission_resource = "TripPlan"
    filter_backends = [PlainRefSearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    # The list's search box matches what the table shows: plan code/id,
    # location (ULB/RLB names), collection type, staff template, vehicle,
    # waste types and approval/status text. Geo/staff/vehicle/ward columns
    # are plain unique_id (or JSON-list) columns with no DB join, so names
    # go through PlainRefSearchFilter's `column=Model.field` syntax.
    search_fields = [
        "display_code",
        "unique_id",
        "collection_type",
        "status",
        "approval_status",
        "state_id=app.models.superadmin.common_masters.state.State.name",
        "district_id=app.models.masters.district.District.name",
        "corporation_id=app.models.masters.corporation.Corporation.corporation_name",
        "municipality_id=app.models.masters.municipality.Municipality.municipality_name",
        "town_panchayat_id=app.models.masters.town_panchayat.TownPanchayat.town_panchayat_name",
        "panchayat_union_id=app.models.masters.panchayat_union.PanchayatUnion.union_name",
        "panchayat_id=app.models.masters.panchayat.Panchayat.panchayat_name",
        "staff_template_id=app.models.core_modules.schedule_setup.staff_template.StaffTemplate.display_code",
        "vehicle_id=app.models.masters.transport_masters.vehicleCreation.VehicleCreation.vehicle_no",
        "waste_type_ids[]=app.models.masters.waste_masters.wastetype.WasteType.waste_type_name",
        "ward_ids[]=app.models.masters.ward.Ward.ward_name",
    ]
    ordering_fields = ["display_code", "status", "approval_status"]
    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "trip-plans"

    def get_queryset(self):
        queryset = super().get_queryset()

        queryset = filter_flat_geo_queryset_by_params(queryset, self.request.query_params)
        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, self.request.user)
        return queryset

    @cache_api("trip_plan_list", vary_on_user=True)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("trip_plan_detail", vary_on_user=True)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

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

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*TRIP_PLAN_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*TRIP_PLAN_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*TRIP_PLAN_CACHE_SCOPES)
