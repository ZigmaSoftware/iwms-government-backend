from app.models.masters.town_panchayat import TownPanchayat
from app.serializers.masters.town_panchayat_serializer import TownPanchayatSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets


class TownPanchayatViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TownPanchayatSerializer
    lookup_field = "unique_id"
    permission_resource = "TownPanchayat"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "town-panchayats"

    def get_queryset(self):
        queryset = TownPanchayat.objects.filter(is_deleted=False)

        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")

        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)
        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
