from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.customers.customercreation import CustomerCreation
from app.models.complaint_ticket.ticket import ComplaintTicket
from app.models.complaint_ticket.status_master import ComplaintStatus


def generate_reopen_history_id():
    return f"CPTRO-{generate_unique_id()}"


class ComplaintReopenHistory(BaseMaster):
    """Audit row written each time a ticket is reopened."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_reopen_history_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="reopen_history",
    )
    reopened_by_customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_reopens",
    )
    reopened_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_reopens",
    )
    reopen_reason = models.TextField(blank=True, null=True)
    previous_status = models.ForeignKey(
        ComplaintStatus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reopen_history",
    )

    reopened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reopened_at"]
        verbose_name = "Complaint Reopen History"
        verbose_name_plural = "Complaint Reopen History"

    def __str__(self):
        return f"{self.ticket_id} reopened"
