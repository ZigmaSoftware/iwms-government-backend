from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from app.models.superadmin.role_management.userType import UserType
from app.serializers.superadmin.role_management.usertype_serializer import UserTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin


class UserTypeViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = UserType.objects.filter(is_deleted=False)
    serializer_class = UserTypeSerializer
    lookup_field = "unique_id"

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

    def perform_destroy(self, instance):
        instance.delete()
