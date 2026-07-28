from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.core_modules.complaint_management.team_master import ComplaintTeam
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails


def generate_assignment_history_id():
    return f"CPTAH-{generate_unique_id()}"


class ComplaintAssignmentHistory(BaseMaster):
    """Audit row written on every ticket (re)assignment."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_assignment_history_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="assignment_history",
    )
    from_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignment_history_from",
    )
    to_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignment_history_to",
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_from",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_to",
    )
    from_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_from_staff",
    )
    to_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_to_staff",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_assignment_by",
    )
    assignment_reason = models.TextField(blank=True, null=True)

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Complaint Assignment History"
        verbose_name_plural = "Complaint Assignment History"

    def __str__(self):
        return f"{self.ticket_id} -> {self.to_team_id}"
