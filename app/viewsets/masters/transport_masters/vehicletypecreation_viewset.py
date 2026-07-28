from django.shortcuts import get_object_or_404

from rest_framework import filters, viewsets
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.serializers.masters.transport_masters.vehicletypecreation_serializer import VehicleTypeCreationSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage


class VehicleTypeCreationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
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
