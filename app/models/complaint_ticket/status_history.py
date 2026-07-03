from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.customers.customercreation import CustomerCreation
from app.models.complaint_ticket.ticket import ComplaintTicket
from app.models.complaint_ticket.status_master import ComplaintStatus


def generate_status_history_id():
    return f"CPTSH-{generate_unique_id()}"


class ComplaintStatusHistory(BaseMaster):
    """Audit row written on every ticket status change."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_status_history_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.ForeignKey(
        ComplaintStatus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="status_history_from",
    )
    to_status = models.ForeignKey(
        ComplaintStatus,
        on_delete=models.PROTECT,
        related_name="status_history_to",
    )
    changed_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_status_changes",
    )
    changed_by_customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_status_changes",
    )
    changed_by_system = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)
    visible_to_citizen = models.BooleanField(default=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Complaint Status History"
        verbose_name_plural = "Complaint Status History"

    def __str__(self):
        return f"{self.ticket_id}: {self.to_status_id}"
