from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.complaint_ticket.notification import ComplaintNotification
from app.serializers.complaint_ticket.notification_serializer import ComplaintNotificationSerializer


class ComplaintNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only feed of the logged-in staff/user's own grievance notifications.

    Staff log in as a StaffcreationOfficeDetails record and Users as the
    platform AUTH_USER_MODEL (see app.authentication.jwt) - scope strictly to
    whichever one made the request so nobody sees another person's alerts.
    """

    serializer_class = ComplaintNotificationSerializer
    queryset = ComplaintNotification.objects.none()
    lookup_field = "unique_id"

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        qs = ComplaintNotification.objects.filter(is_deleted=False).select_related(
            "ticket", "ticket__status"
        )
        if hasattr(user, "staff_unique_id"):
            qs = qs.filter(recipient_staff=user)
        elif getattr(user, "is_authenticated", False):
            qs = qs.filter(recipient_user=user)
        else:
            qs = qs.none()
        return qs.order_by("-created_at")

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread_count": self.get_queryset().filter(is_read=False).count()})

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, unique_id=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        unread = self.get_queryset().filter(is_read=False)
        updated = unread.count()
        unread.update(is_read=True, read_at=timezone.now())
        return Response({"updated": updated})
