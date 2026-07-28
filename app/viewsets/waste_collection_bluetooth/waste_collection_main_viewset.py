from rest_framework import viewsets

from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteCollectionMain
from app.serializers.waste_collection_bluetooth.waste_collection_main_serializer import (
    WasteCollectionMainSerializer,
)


class WasteCollectionMainViewSet(viewsets.ModelViewSet):
    queryset = WasteCollectionMain.objects.filter(is_deleted=False)
    serializer_class = WasteCollectionMainSerializer
    lookup_field = "unique_id"
    permission_resource = "WasteCollectionMain"

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
