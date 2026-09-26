from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

from app.models.core_modules.complaint_management.routing_rule import ComplaintRoutingRule
from app.models.core_modules.complaint_management.feedback import ComplaintFeedback
from app.models.core_modules.complaint_management.reopen_history import ComplaintReopenHistory

from app.serializers.core_modules.complaint_management.transaction_serializers import (
    ComplaintRoutingRuleSerializer,
    ComplaintFeedbackSerializer,
    ComplaintReopenHistorySerializer,
)


class _SoftDeleteMixin:
    CACHE_SCOPES = ()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        if self.CACHE_SCOPES:
            invalidate_on_commit(*self.CACHE_SCOPES)
        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)


class ComplaintRoutingRuleViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_routing_rule"
    queryset = ComplaintRoutingRule.objects.filter(is_deleted=False).order_by("unique_id")
    serializer_class = ComplaintRoutingRuleSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "routing-rules"

    CACHE_SCOPES = ("complaint_routing_rule_list", "complaint_routing_rule_detail")

    @cache_api("complaint_routing_rule_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_routing_rule_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)


class ComplaintFeedbackViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_feedback"
    serializer_class = ComplaintFeedbackSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["ticket_id"]
    ordering_fields = ["submitted_at", "rating"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "feedback"

    def get_queryset(self):
        qs = ComplaintFeedback.objects.filter(is_deleted=False).order_by("-submitted_at")
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        return qs


class ComplaintReopenHistoryViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_reopen_history"
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
