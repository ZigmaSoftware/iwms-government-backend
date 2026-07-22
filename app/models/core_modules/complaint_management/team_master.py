from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.department import Department
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails


def generate_team_id():
    return f"CPTTEAM-{generate_unique_id()}"


class ComplaintTeam(BaseMaster):
    """Teams that complaint tickets are routed/assigned to."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_team_id,
        editable=False,
    )

    team_code = models.CharField(max_length=80, unique=True)
    team_name = models.CharField(max_length=150)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_teams",
    )
    lead_staff = models.ForeignKey(
        StaffcreationOfficeDetails,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="led_complaint_teams",
    )
    escalates_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalation_sources",
    )
    escalation_level = models.IntegerField(default=1)
    is_field_team = models.BooleanField(default=False)

    class Meta:
        ordering = ["team_code"]
        verbose_name = "Complaint Team"
        verbose_name_plural = "Complaint Teams"

    def __str__(self):
        return self.team_name
