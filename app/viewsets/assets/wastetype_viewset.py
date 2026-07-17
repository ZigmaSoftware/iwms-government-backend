from app.models.assets.wastetype import WasteType
from app.serializers.assets.wastetype_serializer import (
    WasteTypeSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets


class WasteTypeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    
    serializer_class = WasteTypeSerializer
    permission_resource = "WasteType"

    AUDIT_MODULE = "waste-bluetooth"
    AUDIT_ENDPOINT = "types"

    def get_queryset(self):
        return WasteType.objects.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
