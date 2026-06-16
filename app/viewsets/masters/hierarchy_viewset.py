from rest_framework.viewsets import ModelViewSet
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.serializers.masters.hierarchy_serializer import AdministrativeHierarchySerializer


class AdministrativeHierarchyViewSet(ModelViewSet):
    queryset = AdministrativeHierarchy.objects.filter(is_deleted=False)
    serializer_class = AdministrativeHierarchySerializer
    lookup_field = "unique_id"
    permission_resource = "AdministrativeHierarchy"