from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.complaint_ticket.ticket import ComplaintTicket
from app.models.complaint_ticket.team_master import ComplaintTeam
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


def generate_escalation_history_id():
    return f"CPTESC-{generate_unique_id()}"


class ComplaintEscalationHistory(BaseMaster):
    """Audit row for each escalation (SLA breach or manual)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_escalation_history_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="escalation_history",
    )
    escalation_level = models.IntegerField(default=1)
    escalated_from_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalation_from",
    )
    escalated_to_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalation_to",
    )
    escalated_to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_escalations",
    )
    escalated_to_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_escalations_staff",
    )
    reason = models.TextField(blank=True, null=True)
    escalated_by_system = models.BooleanField(default=False)

    escalated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-escalated_at"]
        verbose_name = "Complaint Escalation History"
        verbose_name_plural = "Complaint Escalation History"

    def __str__(self):
        return f"{self.ticket_id} esc L{self.escalation_level}"
