from rest_framework import viewsets
from app.models.customers.wastecollection import WasteCollection
from app.serializers.customers.wastecollection_serializer import WasteCollectionSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets

class WasteCollectionViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = WasteCollection.objects.filter(is_deleted=False).select_related(
        "customer__location_node","customer__location_node__level",
        "customer__property_ref","customer__sub_property"
    ).order_by("-collection_date","-collection_time")
    serializer_class = WasteCollectionSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "customer-masters"
    AUDIT_ENDPOINT = "wastecollections" 
