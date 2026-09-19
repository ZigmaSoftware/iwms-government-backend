from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

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
    CACHE_SCOPES = ()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active"])
        if self.CACHE_SCOPES:
            invalidate_on_commit(*self.CACHE_SCOPES)
        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)


class ComplaintSourceViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_source"
    queryset = ComplaintSource.objects.filter(is_deleted=False).order_by("source_code")
    serializer_class = ComplaintSourceSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["source_code", "source_name"]
    ordering_fields = ["source_code", "source_name", "is_active"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "sources"

    CACHE_SCOPES = ("complaint_source_list", "complaint_source_detail")

    @cache_api("complaint_source_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_source_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)


class ComplaintLanguageViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_language"
    queryset = ComplaintLanguage.objects.filter(is_deleted=False).order_by("language_code")
    serializer_class = ComplaintLanguageSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["language_code", "language_name"]
    ordering_fields = ["language_code", "language_name", "is_active"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "languages"

    CACHE_SCOPES = ("complaint_language_list", "complaint_language_detail")

    @cache_api("complaint_language_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_language_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)


class ComplaintPriorityViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_priority"
    queryset = ComplaintPriority.objects.filter(is_deleted=False).order_by("sort_order")
    serializer_class = ComplaintPrioritySerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["priority_code", "priority_name"]
    ordering_fields = ["sort_order", "priority_code", "is_active"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "priorities"

    CACHE_SCOPES = ("complaint_priority_list", "complaint_priority_detail")

    @cache_api("complaint_priority_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_priority_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)


class ComplaintStatusViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_status"
    queryset = ComplaintStatus.objects.filter(is_deleted=False).order_by("sort_order")
    serializer_class = ComplaintStatusSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["status_code", "status_name"]
    ordering_fields = ["sort_order", "status_code", "is_active"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "statuses"

    CACHE_SCOPES = ("complaint_status_list", "complaint_status_detail")

    @cache_api("complaint_status_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_status_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)


class ComplaintTeamViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_team"
    queryset = ComplaintTeam.objects.filter(is_deleted=False).select_related("department").order_by("team_code")
    serializer_class = ComplaintTeamSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["team_code", "team_name", "department__department_name"]
    ordering_fields = ["team_code", "team_name", "is_active"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "teams"

    CACHE_SCOPES = ("complaint_team_list", "complaint_team_detail")

    @cache_api("complaint_team_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_team_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)


class ComplaintModuleViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_module"
    queryset = ComplaintModule.objects.filter(is_deleted=False).order_by("sort_order")
    serializer_class = ComplaintModuleSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["module_code", "module_name"]
    ordering_fields = ["sort_order", "module_code", "is_active"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "modules"

    CACHE_SCOPES = ("complaint_module_list", "complaint_module_detail")

    @cache_api("complaint_module_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_module_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)


class ComplaintCategoryViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_category"
    queryset = ComplaintCategory.objects.filter(is_deleted=False).select_related(
        "default_priority", "default_team", "module"
    ).order_by("sort_order")
    serializer_class = ComplaintCategorySerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["category_code", "category_name", "module__module_name"]
    ordering_fields = ["sort_order", "category_code", "is_active"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "categories"
    permission_exempt_actions = {"list"}

    CACHE_SCOPES = ("complaint_category_list", "complaint_category_detail")

    @cache_api("complaint_category_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_category_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)


class ComplaintSubcategoryViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_subcategory"
    serializer_class = ComplaintSubcategorySerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["subcategory_code", "subcategory_name", "category__category_name"]
    ordering_fields = ["sort_order", "subcategory_code", "is_active"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "subcategories"

    def get_queryset(self):
        qs = ComplaintSubcategory.objects.filter(is_deleted=False).select_related("category").order_by("sort_order")
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        return qs

    CACHE_SCOPES = ("complaint_subcategory_list", "complaint_subcategory_detail")

    @cache_api("complaint_subcategory_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_subcategory_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)


class ComplaintSlaRuleViewSet(_SoftDeleteMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "complaint_sla_rule"
    queryset = ComplaintSlaRule.objects.filter(is_deleted=False).select_related(
        "category", "priority"
    ).order_by("unique_id")
    serializer_class = ComplaintSlaRuleSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["category__category_name", "priority__priority_name"]
    ordering_fields = ["unique_id", "is_active"]
    AUDIT_MODULE = "complaint-ticket"
    AUDIT_ENDPOINT = "sla-rules"

    CACHE_SCOPES = ("complaint_sla_rule_list", "complaint_sla_rule_detail")

    @cache_api("complaint_sla_rule_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("complaint_sla_rule_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*self.CACHE_SCOPES)
