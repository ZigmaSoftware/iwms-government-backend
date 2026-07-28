from app.models.masters.waste_masters.wastetype import WasteType
from app.serializers.masters.waste_masters.wastetype_serializer import (
    WasteTypeSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.lite_serializer_mixin import LiteListMixin, make_lite_serializer
from app.utils.pagination import LimitOffsetWithPage
from rest_framework import filters, viewsets


class WasteTypeViewSet(LiteListMixin, AuditViewSetMixin, viewsets.ModelViewSet):

    serializer_class = WasteTypeSerializer
    lite_serializer_class = make_lite_serializer(WasteType, "waste_type_name")
    permission_resource = "WasteType"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["waste_type_name"]
    ordering_fields = ["waste_type_name", "is_active"]

    AUDIT_MODULE = "waste-bluetooth"
    AUDIT_ENDPOINT = "types"

    def get_queryset(self):
        return WasteType.objects.filter(is_deleted=False)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
