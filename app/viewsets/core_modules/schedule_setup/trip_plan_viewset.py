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

TRIP_PLAN_CACHE_SCOPES = ("trip_plan_list", "trip_plan_detail")


class TripPlanViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "trip_plan"
    queryset = TripPlan.objects.filter(is_deleted=False)

    serializer_class = TripPlanSerializer
    lookup_field = "unique_id"
    swagger_tags = ["Desktop / Operations / Trip Plan"]
    permission_resource = "TripPlan"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["display_code"]
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
