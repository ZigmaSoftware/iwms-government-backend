# app/api/views/area_type_view.py

from rest_framework import viewsets
from app.models.masters.areatype import AreaType
from app.serializers.masters.areatype_serializer import AreaTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin


class AreaTypeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    
    serializer_class = AreaTypeSerializer
    lookup_field = "unique_id"
    permission_resource = "AreaType"

    AUDIT_MODULE = "masters"
    AUDIT_ENDPOINT ="areatype"


    def get_queryset(self):
        queryset = AreaType.objects.filter(is_deleted=False)

        return queryset
    
    def perform_destroy(self, instance):
        instance.delete()