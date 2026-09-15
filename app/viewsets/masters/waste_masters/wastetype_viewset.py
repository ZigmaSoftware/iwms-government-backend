from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.masters.waste_masters.wastetype import WasteType
from app.serializers.masters.waste_masters.wastetype_serializer import (
    WasteTypeSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.lite_serializer_mixin import LiteListMixin, make_lite_serializer
from app.utils.pagination import LimitOffsetWithPage
from rest_framework import filters, viewsets

WASTE_TYPE_CACHE_SCOPES = ("waste_type_list", "waste_type_detail")


class WasteTypeViewSet(LiteListMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "waste_type"

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

    @cache_api("waste_type_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("waste_type_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*WASTE_TYPE_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*WASTE_TYPE_CACHE_SCOPES)

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])
        invalidate_on_commit(*WASTE_TYPE_CACHE_SCOPES)
