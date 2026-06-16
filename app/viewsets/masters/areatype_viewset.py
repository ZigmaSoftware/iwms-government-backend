# app/api/views/area_type_view.py

from rest_framework.viewsets import ModelViewSet
from app.models.masters.areatype import AreaType
from app.serializers.masters.areatype_serializer import AreaTypeSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.utils.audit_mixin import AuditViewSetMixin


class AreaTypeViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    
    serializer_class = AreaTypeSerializer
    lookup_field = "unique_id"
    permission_resource = "AreaType"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="areatype"


    def get_queryset(self):
        queryset = AreaType.objects.filter(is_deleted=False)

        company_uid = self.request.query_params.get("company_id")
        project_uid = self.request.query_params.get("project_id")

        if company_uid:
            queryset = queryset.filter(company_id__unique_id=company_uid)

        if project_uid:
            queryset = queryset.filter(project_id__unique_id=project_uid)

        return queryset
    
    def perform_destroy(self, instance):
        instance.delete()