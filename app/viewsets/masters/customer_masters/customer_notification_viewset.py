from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.masters.customer_masters.customer_notification import (
    CustomerNotification,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.serializers.masters.customer_masters.customer_notification_serializer import (
    CustomerNotificationSerializer,
)
from app.services.push_notification_service import send_push_to_customer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage


class CustomerNotificationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    """Testing screen for sending a sample collection push to customers."""

    serializer_class = CustomerNotificationSerializer
    lookup_field = "unique_id"
    pagination_class = LimitOffsetWithPage
    permission_resource = "CustomerNotification"
    throttle_scope = "customer_notification"

    AUDIT_MODULE = "customer-masters"
    AUDIT_ENDPOINT = "customer-notifications"

    def get_queryset(self):
        return (
            CustomerNotification.objects.filter(is_deleted=False)
            .select_related("customer")
            .order_by("customer__customer_name")
        )

    @action(detail=False, methods=["get"], url_path="customer-options")
    def customer_options(self, request):
        configured = set(
            CustomerNotification.objects.filter(is_deleted=False).values_list(
                "customer_id", flat=True
            )
        )
        queryset = (
            CustomerCreation.objects.filter(is_deleted=False, is_active=True)
            .exclude(unique_id__in=configured)
            .order_by("customer_name")
        )
        return Response(
            [
                {
                    "unique_id": customer.unique_id,
                    "customer_name": customer.customer_name,
                    "contact_no": customer.contact_no,
                    "username": customer.username,
                    "has_fcm_token": bool(customer.fcm_token),
                }
                for customer in queryset[:500]
            ],
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, unique_id=None):
        instance = self.get_object()
        customer = instance.customer
        title = "Collection notification"
        body = "This is a test collection notification from IWMS."
        sent = send_push_to_customer(
            customer,
            title,
            body,
            data={
                "type": "COLLECTION_TEST",
                "customer_id": customer.unique_id,
            },
        )

        instance.last_tested_at = timezone.now()
        instance.last_test_sent = sent
        instance.last_test_message = (
            "Notification sent."
            if sent
            else "Notification was not sent. Check Firebase configuration and customer device token."
        )
        instance.save(
            update_fields=[
                "last_tested_at",
                "last_test_sent",
                "last_test_message",
                "updated_at",
            ]
        )

        return Response(
            {
                "sent": sent,
                "message": instance.last_test_message,
                "customer_id": customer.unique_id,
                "customer_name": customer.customer_name,
            },
            status=status.HTTP_200_OK,
        )
