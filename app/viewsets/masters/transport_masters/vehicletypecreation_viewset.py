from django.shortcuts import get_object_or_404

from rest_framework import filters, viewsets
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.serializers.masters.transport_masters.vehicletypecreation_serializer import VehicleTypeCreationSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

VEHICLE_TYPE_CREATION_CACHE_SCOPES = ("vehicle_type_creation_list", "vehicle_type_creation_detail")


class VehicleTypeCreationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "vehicle_type_creation"
    queryset = VehicleTypeCreation.objects.filter(is_deleted=False)
    serializer_class = VehicleTypeCreationSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["vehicleType", "description"]
    ordering_fields = ["vehicleType", "is_active"]

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "vehicle-types"

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        queryset = self.filter_queryset(self.get_queryset())

        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj

    @cache_api("vehicle_type_creation_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("vehicle_type_creation_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*VEHICLE_TYPE_CREATION_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*VEHICLE_TYPE_CREATION_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*VEHICLE_TYPE_CREATION_CACHE_SCOPES)
