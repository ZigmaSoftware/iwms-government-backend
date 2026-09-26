from rest_framework import filters, viewsets
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.masters.waste_masters.subproperty import SubProperty
from app.serializers.masters.waste_masters.subproperty_serializer import SubPropertySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.utils.plain_ref_search import PlainRefSearchFilter

SUB_PROPERTY_CACHE_SCOPES = ("sub_property_list", "sub_property_detail")

class SubPropertyViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "sub_property"
    queryset = SubProperty.objects.filter(is_deleted=False)\
        .order_by("sub_property_name")

    serializer_class = SubPropertySerializer
    AUDIT_MODULE = "waste-types"
    AUDIT_ENDPOINT = "subproperties"
    lookup_field = "unique_id"
    filter_backends = [PlainRefSearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = [
        "sub_property_name",
        "property_id=app.models.masters.waste_masters.property.Property.property_name",
    ]
    ordering_fields = ["sub_property_name", "is_active"]

    @cache_api("sub_property_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("sub_property_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*SUB_PROPERTY_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*SUB_PROPERTY_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*SUB_PROPERTY_CACHE_SCOPES)
