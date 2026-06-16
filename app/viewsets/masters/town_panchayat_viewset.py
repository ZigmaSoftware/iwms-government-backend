from app.models.masters.town_panchayat import TownPanchayat
from app.serializers.masters.town_panchayat_serializer import TownPanchayatSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class TownPanchayatViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = TownPanchayatSerializer
    lookup_field = "unique_id"
    permission_resource = "TownPanchayat"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT = "town-panchayats"

    def get_queryset(self):
        queryset = TownPanchayat.objects.filter(is_deleted=False)

        company_uid = self.request.query_params.get("company_id")
        project_uid = self.request.query_params.get("project_id")
        district_uid = self.request.query_params.get("district") or self.request.query_params.get("district_id")
        state_uid = self.request.query_params.get("state") or self.request.query_params.get("state_id")

        if company_uid:
            queryset = queryset.filter(company_id__unique_id=company_uid)
        if project_uid:
            queryset = queryset.filter(project_id__unique_id=project_uid)
        if district_uid:
            queryset = queryset.filter(district_id__unique_id=district_uid)
        if state_uid:
            queryset = queryset.filter(state_id__unique_id=state_uid)

        return queryset

    def perform_destroy(self, instance):
        instance.delete()
