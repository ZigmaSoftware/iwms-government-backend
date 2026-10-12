from rest_framework import viewsets

from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteCollectionMain
from app.serializers.waste_collection_bluetooth.waste_collection_main_serializer import (
    WasteCollectionMainSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin


class WasteCollectionMainViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "waste_collection_main"
    queryset = WasteCollectionMain.objects.filter(is_deleted=False)
    serializer_class = WasteCollectionMainSerializer
    lookup_field = "unique_id"
    permission_resource = "WasteCollectionMain"
    AUDIT_MODULE = "waste-collection-bluetooth"
    AUDIT_ENDPOINT = "waste-collection-main"

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
