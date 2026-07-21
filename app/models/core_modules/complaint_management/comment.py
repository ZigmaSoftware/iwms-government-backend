from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.complaint_management.ticket import ComplaintTicket


def generate_comment_id():
    return f"CPTCMT-{generate_unique_id()}"


class ComplaintComment(BaseMaster):
    """Comments / notes on a complaint ticket (internal or citizen-facing)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_comment_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    comment_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_comments",
    )
    comment_by_customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_comments",
    )
    comment_text = models.TextField()
    is_internal = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Comment"
        verbose_name_plural = "Complaint Comments"

    def __str__(self):
        return f"{self.ticket_id} comment {self.unique_id}"
