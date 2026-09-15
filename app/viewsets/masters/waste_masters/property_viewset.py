from rest_framework import filters, viewsets
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.masters.waste_masters.property import Property
from app.serializers.masters.waste_masters.property_serializer import PropertySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

PROPERTY_CACHE_SCOPES = ("property_list", "property_detail")

class PropertyViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "property"
    queryset = Property.objects.filter(is_deleted=False)
    serializer_class = PropertySerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["property_name"]
    ordering_fields = ["property_name", "is_active"]

    AUDIT_MODULE = "waste-types"
    AUDIT_ENDPOINT = "properties"

    @cache_api("property_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("property_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*PROPERTY_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*PROPERTY_CACHE_SCOPES)

    def perform_destroy(self, instance):
        instance.delete()  # soft delete
        invalidate_on_commit(*PROPERTY_CACHE_SCOPES)
