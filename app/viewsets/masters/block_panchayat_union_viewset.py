from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.masters.block_panchayat_union import BlockPanchayatUnion
from app.serializers.masters.block_panchayat_union_serializer import BlockPanchayatUnionSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets

BLOCK_PANCHAYAT_UNION_CACHE_SCOPES = ("block_panchayat_union_list", "block_panchayat_union_detail")


class BlockPanchayatUnionViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "block_panchayat_union"
    serializer_class = BlockPanchayatUnionSerializer
    lookup_field = "unique_id"
    permission_resource = "BlockPanchayatUnion"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "block-panchayat-unions"

    def get_queryset(self):
        queryset = BlockPanchayatUnion.objects.filter(is_deleted=False)

        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)
        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        return queryset

    @cache_api("block_panchayat_union_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("block_panchayat_union_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*BLOCK_PANCHAYAT_UNION_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*BLOCK_PANCHAYAT_UNION_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*BLOCK_PANCHAYAT_UNION_CACHE_SCOPES)
