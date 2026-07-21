from rest_framework import status, viewsets
from rest_framework.response import Response

from app.utils.audit_mixin import AuditViewSetMixin

from app.models.core_modules.complaint_management.source_master import ComplaintSource
from app.models.core_modules.complaint_management.language_master import ComplaintLanguage
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.team_master import ComplaintTeam
from app.models.core_modules.complaint_management.module_master import ComplaintModule
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.subcategory_master import ComplaintSubcategory
from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule

from app.serializers.core_modules.complaint_management.master_serializers import (
    ComplaintSourceSerializer,
    ComplaintLanguageSerializer,
    ComplaintPrioritySerializer,
    ComplaintStatusSerializer,
    ComplaintTeamSerializer,
    ComplaintModuleSerializer,
    ComplaintCategorySerializer,
    ComplaintSubcategorySerializer,
    ComplaintSlaRuleSerializer,
)


class _SoftDeleteMixin:
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)


class ComplaintSourceViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintSource.objects.filter(is_deleted=False).order_by("source_code")
    serializer_class = ComplaintSourceSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "sources"


class ComplaintLanguageViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintLanguage.objects.filter(is_deleted=False).order_by("language_code")
    serializer_class = ComplaintLanguageSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "languages"


class ComplaintPriorityViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintPriority.objects.filter(is_deleted=False).order_by("sort_order")
    serializer_class = ComplaintPrioritySerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "priorities"


class ComplaintStatusViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintStatus.objects.filter(is_deleted=False).order_by("sort_order")
    serializer_class = ComplaintStatusSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "statuses"


class ComplaintTeamViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintTeam.objects.filter(is_deleted=False).select_related("department").order_by("team_code")
    serializer_class = ComplaintTeamSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "teams"


class ComplaintModuleViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintModule.objects.filter(is_deleted=False).order_by("sort_order")
    serializer_class = ComplaintModuleSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "modules"


class ComplaintCategoryViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintCategory.objects.filter(is_deleted=False).select_related(
        "default_priority", "default_team", "module"
    ).order_by("sort_order")
    serializer_class = ComplaintCategorySerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "categories"
    permission_exempt_actions = {"list"}


class ComplaintSubcategoryViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ComplaintSubcategorySerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "subcategories"

    def get_queryset(self):
        qs = ComplaintSubcategory.objects.filter(is_deleted=False).select_related("category").order_by("sort_order")
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        return qs


class ComplaintSlaRuleViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = ComplaintSlaRule.objects.filter(is_deleted=False).select_related(
        "category", "priority"
    ).order_by("unique_id")
    serializer_class = ComplaintSlaRuleSerializer
    lookup_field = "unique_id"
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "sla-rules"
