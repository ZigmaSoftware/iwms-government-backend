from django.core.cache import cache
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.masters.customer_masters.customer_access_configuration import (
    CustomerAccessConfiguration,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.serializers.masters.customer_masters.customer_access_configuration_serializer import (
    CustomerAccessConfigurationSerializer,
)
from app.utils.app_feature_grants import CITIZEN_APP_SCREENS
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.utils.permission_snapshot import (
    EMPTY_SNAPSHOT,
    customer_access_snapshot,
    write_customer_access_audit,
)


class CustomerAccessConfigurationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """Customer Access Configuration — the customer counterpart of Staff
    Access Configuration.

    Customers are not staff, so they cannot hang grants off a
    StaffAccessConfiguration, and they have no web screens to inherit. This
    screen ticks the app they may sign into and the citizen screens they see.
    """
    throttle_scope = "customer_access_configuration"

    serializer_class = CustomerAccessConfigurationSerializer
    lookup_field = "customer_unique_id"
    pagination_class = LimitOffsetWithPage
    permission_resource = "CustomerAccessConfiguration"

    AUDIT_MODULE = "customer-masters"
    AUDIT_ENDPOINT = "customer-access-configuration"

    def get_queryset(self):
        return CustomerAccessConfiguration.objects.filter(is_deleted=False)

    def get_object(self):
        customer_id = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        obj = self.get_queryset().filter(customer_id=customer_id).first()
        if not obj:
            from django.http import Http404

            raise Http404
        self.check_object_permissions(self.request, obj)
        return obj

    # Each save writes ONE User Access Audit row holding the customer's
    # whole access before and after it (app/utils/permission_snapshot.py).

    def perform_create(self, serializer):
        # Create re-uses a customer's existing configuration, so the save may
        # be an update of access they already had.
        customer = serializer.validated_data.get("resolved_customer")
        existing = (
            CustomerAccessConfiguration.objects.filter(
                customer_id=customer.unique_id, is_deleted=False
            ).first()
            if customer
            else None
        )
        before = customer_access_snapshot(existing)
        instance = serializer.save()
        write_customer_access_audit(
            self.request, instance, before, customer_access_snapshot(instance),
            "UPDATED" if existing else "CREATED",
        )
        cache.clear()

    def perform_update(self, serializer):
        before = customer_access_snapshot(serializer.instance)
        instance = serializer.save()
        write_customer_access_audit(
            self.request, instance, before, customer_access_snapshot(instance), "UPDATED"
        )
        cache.clear()

    def perform_destroy(self, instance):
        before = customer_access_snapshot(instance)
        super().perform_destroy(instance)
        write_customer_access_audit(self.request, instance, before, EMPTY_SNAPSHOT, "DELETED")
        cache.clear()

    @action(detail=False, methods=["get"], url_path="available-screens")
    def available_screens(self, request):
        """The citizen app screens and modules this form can tick."""
        screens = UserScreen.objects.filter(
            userscreen_name__in=CITIZEN_APP_SCREENS, is_deleted=False
        ).order_by("order_no")
        modules = AppModule.objects.filter(
            surface_key="citizen", is_active=True, is_deleted=False
        )
        return Response({
            "app_modules": [
                {"uniqueId": m.unique_id, "surfaceKey": m.surface_key, "label": m.label}
                for m in modules
            ],
            "screens": [
                {
                    "userScreenId": s.unique_id,
                    "userScreenName": s.userscreen_name,
                    "label": s.userscreen_name.replace("app-citizen-", "").title(),
                }
                for s in screens
            ],
        })

    @action(detail=False, methods=["get"], url_path="customer-options")
    def customer_options(self, request):
        """Customers available to configure, flagged if already done."""
        queryset = CustomerCreation.objects.filter(
            is_deleted=False, is_active=True
        ).order_by("customer_name")

        configured = set(
            CustomerAccessConfiguration.objects.filter(
                customer_id__in=queryset.values_list("unique_id", flat=True),
                is_deleted=False,
            ).values_list("customer_id", flat=True)
        )

        return Response(
            [
                {
                    "unique_id": c.unique_id,
                    "customer_name": c.customer_name,
                    "contact_no": c.contact_no,
                    "username": c.username,
                    "app_module": c.app_module,
                    "has_access_configuration": c.unique_id in configured,
                }
                for c in queryset[:500]
            ],
            status=status.HTTP_200_OK,
        )
