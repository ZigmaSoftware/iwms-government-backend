from django.db.models import Q
from rest_framework import filters, viewsets

from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.staffHierarchy import StaffHierarchy
from app.serializers.superadmin.role_management.staffhierarchy_serializer import StaffHierarchySerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.utils.staff_hierarchy import SCOPE_FIELDS

STAFF_HIERARCHY_CACHE_SCOPES = ("staff_hierarchy_list", "staff_hierarchy_detail")


class StaffHierarchyViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "staff_hierarchy"
    queryset = StaffHierarchy.objects.filter(is_deleted=False)
    serializer_class = StaffHierarchySerializer
    lookup_field = "unique_id"
    pagination_class = LimitOffsetWithPage
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["hierarchy_level", "created_at", "is_active"]

    AUDIT_MODULE = "role-assigns"
    AUDIT_ENDPOINT = "staff-hierarchy"

    permission_resource = "StaffHierarchy"

    def get_queryset(self):
        queryset = StaffHierarchy.objects.filter(is_deleted=False)
        params = self.request.query_params

        is_active = params.get("is_active")
        if is_active in ("true", "1", "True"):
            queryset = queryset.filter(is_active=True)
        elif is_active in ("false", "0", "False"):
            queryset = queryset.filter(is_active=False)

        # ?district_id= etc. narrow the list to rows scoped to that place.
        for field in SCOPE_FIELDS:
            value = params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})

        # Role names live on GovernmentStaffUserType (as choice keys with
        # display labels), not on this table, so ?search= is resolved to the
        # matching role ids first and applied to either side of the mapping.
        search = (params.get("search") or "").strip().lower()
        if search:
            role_labels = dict(GovernmentStaffUserType.GOVT_ROLE_CHOICES)
            level_labels = dict(GovernmentStaffUserType.GOVT_LEVEL_CHOICES)
            role_ids = [
                unique_id
                for unique_id, name, level in GovernmentStaffUserType.objects.filter(
                    is_deleted=False
                ).values_list("unique_id", "name", "level")
                if search in name.lower()
                or search in role_labels.get(name, "").lower()
                or search in level_labels.get(level, "").lower()
            ]
            queryset = queryset.filter(
                Q(governmentusertype_id__in=role_ids)
                | Q(reports_to_governmentusertype_id__in=role_ids)
            )

        return queryset

    @cache_api("staff_hierarchy_list", vary_on_user=False)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("staff_hierarchy_detail", vary_on_user=False)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*STAFF_HIERARCHY_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*STAFF_HIERARCHY_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*STAFF_HIERARCHY_CACHE_SCOPES)
