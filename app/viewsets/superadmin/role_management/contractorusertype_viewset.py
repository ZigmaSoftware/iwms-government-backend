from rest_framework.response import Response
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.serializers.superadmin.role_management.contractorusertype_serializer import ContractorUserTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

CONTRACTOR_USER_TYPE_CACHE_SCOPES = ("contractor_user_type_list", "contractor_user_type_detail")


class ContractorUserTypeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "contractor_user_type"
    queryset = ContractorUserType.objects.filter(is_deleted=False)
    serializer_class = ContractorUserTypeSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["name"]
    ordering_fields = ["name", "is_active"]

    AUDIT_MODULE = "role-assigns"
    AUDIT_ENDPOINT = "contractor-user-type"

    permission_resource = "ContractorUserType"

    @cache_api("contractor_user_type_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("contractor_user_type_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*CONTRACTOR_USER_TYPE_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*CONTRACTOR_USER_TYPE_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*CONTRACTOR_USER_TYPE_CACHE_SCOPES)

    @action(detail=False, methods=["get"], url_path="role-choices")
    def role_choices(self, request):
        user = request.user

        choices = ContractorUserType.CONTRACTOR_ROLE_CHOICES

        # 🔐 Optional: restrict roles based on logged-in user
        if not user.is_superuser:
            choices = [c for c in choices if c[0] != "superadmin"]
        return Response([
            {"value": key, "label": label}
            for key, label in ContractorUserType.CONTRACTOR_ROLE_CHOICES
        ])
