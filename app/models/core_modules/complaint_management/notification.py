from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


def generate_notification_id():
    return f"CPTNTF-{generate_unique_id()}"


class ComplaintNotification(BaseMaster):
    """In-app notification for a grievance event (assign/escalate/resolve/reopen).

    Delivered to whichever party is currently handling the ticket - a staff
    login (``recipient_staff``, the common case) or a platform User login
    (``recipient_user``, e.g. auto-routing to an AUTH_USER_MODEL owner).
    """

    EVENT_ASSIGNED = "ASSIGNED"
    EVENT_ESCALATED = "ESCALATED"
    EVENT_ESCALATED_TO = "ESCALATED_TO"
    EVENT_RESOLVED = "RESOLVED"
    EVENT_REOPENED = "REOPENED"

    EVENT_CHOICES = [
        (EVENT_ASSIGNED, "Assigned"),
        (EVENT_ESCALATED, "Escalated"),
        (EVENT_ESCALATED_TO, "Escalated To You"),
        (EVENT_RESOLVED, "Resolved"),
        (EVENT_REOPENED, "Reopened"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_notification_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    recipient_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="complaint_notifications",
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="complaint_notifications",
    )

    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, null=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Complaint Notification"
        verbose_name_plural = "Complaint Notifications"
        indexes = [
            models.Index(fields=["recipient_staff", "is_read"]),
            models.Index(fields=["recipient_user", "is_read"]),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.ticket_id}"
