from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.waste_types.property import Property
from app.serializers.waste_types.property_serializer import PropertySerializer
from app.utils.audit_mixin import AuditViewSetMixin

class PropertyViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "waste-types"
    AUDIT_ENDPOINT = "properties"

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
