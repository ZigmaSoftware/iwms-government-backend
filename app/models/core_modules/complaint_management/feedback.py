from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.complaint_management.ticket import ComplaintTicket


def generate_feedback_id():
    return f"CPTFB-{generate_unique_id()}"


class ComplaintFeedback(BaseMaster):
    """Citizen feedback captured after resolution (one per ticket)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_feedback_id,
        editable=False,
    )

    ticket = models.OneToOneField(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_feedback",
    )
    rating = models.IntegerField(null=True, blank=True)
    feedback_text = models.TextField(blank=True, null=True)
    is_issue_solved = models.BooleanField(default=False)

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Complaint Feedback"
        verbose_name_plural = "Complaint Feedback"

    def __str__(self):
        return f"{self.ticket_id} feedback {self.rating}"
