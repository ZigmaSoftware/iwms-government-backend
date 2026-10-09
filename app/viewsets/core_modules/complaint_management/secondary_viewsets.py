from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.utils.plain_ref_search import PlainRefSearchFilter

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
    filter_backends = [PlainRefSearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    # The list's search box matches what the table shows: ticket number,
    # customer and feedback text. ticket/customer are plain id columns with
    # no DB join, so names go through PlainRefSearchFilter.
    search_fields = [
        "unique_id",
        "ticket_id",
        "feedback_text",
        "ticket_id=app.models.core_modules.complaint_management.ticket.ComplaintTicket.ticket_no",
        "customer_id=app.models.masters.customer_masters.customercreation.CustomerCreation.customer_name",
    ]
    ordering_fields = ["submitted_at", "rating"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "feedback"

    def get_queryset(self):
        qs = ComplaintFeedback.objects.filter(is_deleted=False).order_by("-submitted_at")
        ticket = self.request.query_params.get("ticket")
        if ticket:
            qs = qs.filter(ticket_id=ticket)
        # Feedback list page's Filters panel.
        issue_solved = str(self.request.query_params.get("is_issue_solved", "")).strip().lower()
        if issue_solved in ("true", "false"):
            qs = qs.filter(is_issue_solved=issue_solved == "true")
        rating = self.request.query_params.get("rating")
        if rating and str(rating).isdigit():
            qs = qs.filter(rating=int(rating))
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
