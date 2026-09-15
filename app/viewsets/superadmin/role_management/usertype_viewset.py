from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.superadmin.role_management.userType import UserType
from app.serializers.superadmin.role_management.usertype_serializer import UserTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage

USER_TYPE_CACHE_SCOPES = ("user_type_list", "user_type_detail")


class UserTypeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "user_type"
    queryset = UserType.objects.filter(is_deleted=False)
    serializer_class = UserTypeSerializer
    lookup_field = "unique_id"
    pagination_class = LimitOffsetWithPage
    search_fields = ["name"]
    ordering_fields = ["name", "is_active"]

    AUDIT_MODULE = "role-assigns"
    AUDIT_ENDPOINT = "user-type"

    permission_resource = "UserType"

    def filter_queryset(self, queryset):
        """
        Override to prevent company-scoped filtering.
        UserTypes are global records and should be accessible to all
        authenticated users.
        """
        # Apply parent search/ordering filters but skip company scoping
        from rest_framework.filters import SearchFilter, OrderingFilter
        queryset = SearchFilter().filter_queryset(self.request, queryset, self)
        queryset = OrderingFilter().filter_queryset(self.request, queryset, self)
        return queryset

    @cache_api("user_type_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("user_type_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*USER_TYPE_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*USER_TYPE_CACHE_SCOPES)

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_on_commit(*USER_TYPE_CACHE_SCOPES)
