from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.serializers.core_modules.notifications.staff_notification_serializer import (
    StaffNotificationSerializer,
)


class StaffNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only feed of the logged-in staff's own in-app notifications
    (vehicle replacement approval/rejection, team changes, substitutions) —
    shared by the driver, operator, and supervisor apps. Scoped strictly to
    whichever staff login made the request.
    """

    serializer_class = StaffNotificationSerializer
    queryset = StaffNotification.objects.none()
    lookup_field = "unique_id"

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if not hasattr(user, "staff_unique_id"):
            return StaffNotification.objects.none()
        return (
            StaffNotification.objects.filter(
                recipient_staff=user, is_deleted=False
            )
            .order_by("-created_at")
        )

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
