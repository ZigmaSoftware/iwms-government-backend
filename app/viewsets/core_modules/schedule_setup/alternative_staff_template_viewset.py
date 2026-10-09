from django.db.models import Q
from rest_framework import filters, viewsets, serializers
from rest_framework.exceptions import NotAuthenticated

from app.utils.plain_ref_search import PlainRefSearchFilter
from app.utils.plain_ref import json_contains_any
from app.cache.decorators import cache_api
from app.cache.invalidation import invalidate_on_commit
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.serializers.core_modules.schedule_setup.alternative_staff_template_serializer import (
    AlternativeStaffTemplateSerializer
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
)
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.services.staff_notification_service import notify_staff
from app.utils.pagination import LimitOffsetWithPage

ALTERNATIVE_STAFF_TEMPLATE_CACHE_SCOPES = (
    "alternative_staff_template_list",
    "alternative_staff_template_detail",
)


class AlternativeStaffTemplateViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """
    API Contract:
    - Create alternative staff mapping
    - Filter by date, template
    """
    throttle_scope = "alternative_staff_template"

    # staff_template / driver / operator are plain unique_ids
    # now (no DB relation) — nothing to select_related.
    queryset = AlternativeStaffTemplate.objects.all()
    serializer_class = AlternativeStaffTemplateSerializer

    #  CRITICAL: single source of truth for middleware
    permission_resource = "AlternativeStaffTemplate"
    lookup_field = "unique_id"
    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    # the list's search box matches what the table shows: template id,
    # staff template, driver, operator, extra operators and the reason
    search_fields = [
        "unique_id",
        "display_code",
        "change_reason",
        "change_remarks",
        "staff_template_id",
        "staff_template_id=app.models.core_modules.schedule_setup.staff_template.StaffTemplate.display_code",
        "driver_id=app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails.employee_name",
        "operator_id=app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails.employee_name",
        "extra_operator_id[]=app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails.employee_name",
    ]
    ordering_fields = ["from_date", "to_date"]

    AUDIT_MODULE = "user-creations"
    AUDIT_ENDPOINT = "alternative-staff-templates"

    def _apply_list_search(self, qs):
        terms = PlainRefSearchFilter().get_search_terms(self.request)
        if not terms:
            return qs

        for term in terms:
            matching_template_ids = StaffTemplate.objects.filter(
                Q(unique_id__icontains=term) | Q(display_code__icontains=term)
            ).values("unique_id")

            matching_staff_ids = StaffcreationOfficeDetails.objects.filter(
                Q(staff_unique_id__icontains=term) | Q(employee_name__icontains=term),
                is_deleted=False,
            ).values_list("staff_unique_id", flat=True)

            clause = (
                Q(unique_id__icontains=term)
                | Q(display_code__icontains=term)
                | Q(staff_template_id__icontains=term)
                | Q(staff_template_id__in=matching_template_ids)
                | Q(change_reason__icontains=term)
                | Q(change_remarks__icontains=term)
                | Q(driver_id__in=matching_staff_ids)
                | Q(operator_id__in=matching_staff_ids)
                | json_contains_any("extra_operator_id", matching_staff_ids)
            )
            qs = qs.filter(clause)

        return qs

    def get_queryset(self):
        qs = super().get_queryset()

        staff_template = self.request.query_params.get("staff_template")
        from_date = self.request.query_params.get("from_date")
        to_date = self.request.query_params.get("to_date")

        if staff_template:
            qs = qs.filter(staff_template_id=staff_template)

        if from_date:
            qs = qs.filter(from_date__gte=from_date)

        if to_date:
            qs = qs.filter(to_date__lte=to_date)

        qs = filter_flat_geo_queryset_by_params(qs, self.request.query_params)
        qs = filter_flat_geo_queryset_by_requester_scope(qs, self.request.user)
        qs = self._apply_list_search(qs)

        return qs

    @cache_api("alternative_staff_template_list", vary_on_user=True)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("alternative_staff_template_detail", vary_on_user=True)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        instance = serializer.save(
            # requested_by=user,  # can be None if allowed in model
        )

        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=new_data
        )

        invalidate_on_commit(*ALTERNATIVE_STAFF_TEMPLATE_CACHE_SCOPES)

    def perform_update(self, serializer):

        if not self.request.user.is_authenticated:
            raise NotAuthenticated("Authentication required")

        previous_data = self._serialize_instance(serializer.instance)

        instance = serializer.save()

        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=new_data
        )

        if (
            previous_data.get("driver_id") != new_data.get("driver_id")
            or previous_data.get("operator_id") != new_data.get("operator_id")
            or previous_data.get("staff_template_id") != new_data.get("staff_template_id")
        ):
            for staff in (instance.driver, instance.operator):
                notify_staff(
                    staff,
                    StaffNotification.TYPE_TEAM_SUBSTITUTED,
                    title="You've been added to a team",
                    body=(
                        f"You've been substituted onto team "
                        f"{getattr(instance.staff_template, 'display_code', instance.staff_template_id)}"
                        + (
                            f" from {instance.from_date} to {instance.to_date}."
                            if instance.from_date and instance.to_date
                            else "."
                        )
                    ),
                    data={
                        "staff_template_id": instance.staff_template_id,
                        "alternative_staff_template_id": instance.unique_id,
                    },
                )

        invalidate_on_commit(*ALTERNATIVE_STAFF_TEMPLATE_CACHE_SCOPES)

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        invalidate_on_commit(*ALTERNATIVE_STAFF_TEMPLATE_CACHE_SCOPES)
