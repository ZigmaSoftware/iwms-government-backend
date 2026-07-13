from rest_framework import viewsets
from app.models.customers.wastecollection import WasteCollection
from app.serializers.customers.wastecollection_serializer import WasteCollectionSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets

class WasteCollectionViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = WasteCollection.objects.filter(is_deleted=False).select_related(
        "customer__state", "customer__district", "customer__area_type",
        "customer__corporation", "customer__municipality", "customer__town_panchayat",
        "customer__panchayat_union", "customer__panchayat",
        "customer__property_ref", "customer__sub_property",
        # record-level geography
        "state", "district", "area_type",
        "corporation", "municipality", "town_panchayat",
        "panchayat_union", "panchayat",
    ).order_by("-collection_date","-collection_time")
    serializer_class = WasteCollectionSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "schedule-masters"
    AUDIT_ENDPOINT = "wastecollections"
