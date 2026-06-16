from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.serializers.waste_collection_bluetooth.waste_type_serializer import (
    WasteTypeSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin


class WasteTypeViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    
    serializer_class = WasteTypeSerializer
    permission_resource = "WasteType"

    AUDIT_MODULE = "waste-bluetooth"
    AUDIT_ENDPOINT = "types"

    def get_queryset(self):
        return WasteType.objects.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
