from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.customers.wastecollection import WasteCollection
from app.serializers.customers.wastecollection_serializer import WasteCollectionSerializer
from app.utils.audit_mixin import AuditViewSetMixin

class WasteCollectionViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    queryset = WasteCollection.objects.filter(is_deleted=False).select_related(
        "customer__ward","customer__zone","customer__city",
        "customer__district","customer__state","customer__country",
        "customer__panchayat_id",
        "customer__property_ref","customer__sub_property"
    ).order_by("-collection_date","-collection_time")
    serializer_class = WasteCollectionSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "customer-masters"
    AUDIT_ENDPOINT = "wastecollections" 
