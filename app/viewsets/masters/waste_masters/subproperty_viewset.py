from rest_framework import viewsets
from app.models.masters.waste_masters.subproperty import SubProperty
from app.serializers.masters.waste_masters.subproperty_serializer import SubPropertySerializer
from app.utils.audit_mixin import AuditViewSetMixin

class SubPropertyViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = SubProperty.objects.filter(is_deleted=False)\
        .select_related("property_id")\
        .order_by("sub_property_name")

    serializer_class = SubPropertySerializer
    AUDIT_MODULE = "waste-types"
    AUDIT_ENDPOINT = "subproperties"
    lookup_field = "unique_id"

    def perform_destroy(self, instance):
        instance.delete()
