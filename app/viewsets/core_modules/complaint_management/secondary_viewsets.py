from rest_framework import status, viewsets
from rest_framework.response import Response

from app.utils.audit_mixin import AuditViewSetMixin

from app.models.core_modules.complaint_management.routing_rule import ComplaintRoutingRule
from app.models.core_modules.complaint_management.feedback import ComplaintFeedback
from app.models.core_modules.complaint_management.reopen_history import ComplaintReopenHistory

from app.serializers.core_modules.complaint_management.transaction_serializers import (
    ComplaintRoutingRuleSerializer,
    ComplaintFeedbackSerializer,
    ComplaintReopenHistorySerializer,
)


class _SoftDeleteMixin:
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)


class ComplaintRoutingRuleViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintRoutingRule.objects.filter(is_deleted=False).select_related(
        "category", "team"
    ).order_by("unique_id")
    serializer_class = ComplaintRoutingRuleSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "routing-rules"


class ComplaintFeedbackViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintFeedbackSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "feedback"

    def get_queryset(self):
        qs = ComplaintFeedback.objects.filter(is_deleted=False).select_related(
            "ticket", "customer"
        ).order_by("-submitted_at")
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        return qs


class ComplaintReopenHistoryViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintReopenHistorySerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "reopen-history"

    def get_queryset(self):
        qs = ComplaintReopenHistory.objects.filter(is_deleted=False).order_by("-reopened_at")
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        return qs
