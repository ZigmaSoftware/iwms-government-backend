from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


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

    ticket_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    recipient_staff_id = models.CharField(max_length=30, null=True, blank=True)
    recipient_user_id = models.CharField(max_length=100, null=True, blank=True)

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
            models.Index(fields=["recipient_staff_id", "is_read"]),
            models.Index(fields=["recipient_user_id", "is_read"]),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.ticket_id}"

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def ticket(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.ticket.ComplaintTicket",
            self.ticket_id,
        )

    @property
    def recipient_staff(self):
        return self._lookup(
            "app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails",
            self.recipient_staff_id,
            field="staff_unique_id",
        )

    @property
    def recipient_user(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User",
            self.recipient_user_id,
        )
