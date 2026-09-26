from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


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

    ticket_id = models.CharField(db_index=True, max_length=30)
    escalation_level = models.IntegerField(default=1)
    escalated_from_team_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    escalated_to_team_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    escalated_to_user_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    escalated_to_staff_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    escalated_by_system = models.BooleanField(default=False)

    escalated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-escalated_at"]
        verbose_name = "Complaint Escalation History"
        verbose_name_plural = "Complaint Escalation History"

    def __str__(self):
        return f"{self.ticket_id} esc L{self.escalation_level}"

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
    def escalated_from_team(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.team_master.ComplaintTeam",
            self.escalated_from_team_id,
        )

    @property
    def escalated_to_team(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.team_master.ComplaintTeam",
            self.escalated_to_team_id,
        )

    @property
    def escalated_to_user(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User",
            self.escalated_to_user_id,
        )

    @property
    def escalated_to_staff(self):
        return self._lookup(
            "app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails",
            self.escalated_to_staff_id,
            field="staff_unique_id",
        )
