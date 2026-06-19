from rest_framework import viewsets

from app.models.user_creations.waste_collection_bluetooth import WasteCollectionSub
from app.serializers.waste_collection_bluetooth.waste_collection_sub_serializer import (
    WasteCollectionSubSerializer,
)


class WasteCollectionSubViewSet(viewsets.ModelViewSet):
    queryset = WasteCollectionSub.objects.filter(is_deleted=False)
    serializer_class = WasteCollectionSubSerializer
    lookup_field = "unique_id"
    permission_resource = "WasteCollectionSub"

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
