from rest_framework import filters, viewsets
from app.models.masters.waste_masters.property import Property
from app.serializers.masters.waste_masters.property_serializer import PropertySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

class PropertyViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["property_name"]
    ordering_fields = ["property_name", "is_active"]

    AUDIT_MODULE = "waste-types"
    AUDIT_ENDPOINT = "properties"

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
