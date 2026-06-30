from rest_framework import viewsets, status
from rest_framework.response import Response
from app.models.grivences.complaints import Complaint
from app.serializers.grivences.complaint_serializer import ComplaintSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from rest_framework import viewsets

class ComplaintViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintSerializer
    lookup_field = "unique_id"
    queryset = Complaint.objects.filter(is_deleted=False).select_related(
        "customer",
        "customer__location_node",
        "customer__location_node__level",
    )

    AUDIT_MODULE = "grivences"
    AUDIT_ENDPOINT = "complaints"

    def get_queryset(self):
        qs = Complaint.objects.filter(is_deleted=False)
        customer_id = self.request.query_params.get("customer") or self.request.query_params.get("customer_id")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response({"message": "Complaint deleted successfully"}, status=status.HTTP_200_OK)
