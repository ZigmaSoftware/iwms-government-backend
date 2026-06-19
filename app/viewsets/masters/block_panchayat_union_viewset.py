from app.models.masters.block_panchayat_union import BlockPanchayatUnion
from app.serializers.masters.block_panchayat_union_serializer import BlockPanchayatUnionSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets


class BlockPanchayatUnionViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
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

    def perform_destroy(self, instance):
        instance.delete()
