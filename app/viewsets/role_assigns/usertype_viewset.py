from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.role_assigns.userType import UserType
from app.serializers.role_assigns.usertype_serializer import UserTypeSerializer
from app.utils.audit_mixin import AuditViewSetMixin


class UserTypeViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    queryset = UserType.objects.filter(is_deleted=False)
    serializer_class = UserTypeSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "role-assigns"
    AUDIT_ENDPOINT = "user-type"

    permission_resource = "UserType"

    def filter_queryset(self, queryset):
        """
        Override to prevent company-scoped filtering.
        UserTypes are global records (company_id=None) and should be accessible 
        to all authenticated users regardless of their company assignment.
        """
        # Apply parent search/ordering filters but skip company scoping
        from rest_framework.filters import SearchFilter, OrderingFilter
        queryset = SearchFilter().filter_queryset(self.request, queryset, self)
        queryset = OrderingFilter().filter_queryset(self.request, queryset, self)
        return queryset

    def perform_destroy(self, instance):
        instance.delete()
