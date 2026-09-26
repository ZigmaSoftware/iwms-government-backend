from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


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

    ticket_id = models.CharField(db_index=True, max_length=30)
    from_team_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    to_team_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    from_user_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    to_user_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    from_staff_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    to_staff_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    assigned_by_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    assignment_reason = models.TextField(blank=True, null=True)

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Complaint Assignment History"
        verbose_name_plural = "Complaint Assignment History"

    def __str__(self):
        return f"{self.ticket_id} -> {self.to_team_id}"

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
    def from_team(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.team_master.ComplaintTeam",
            self.from_team_id,
        )

    @property
    def to_team(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.team_master.ComplaintTeam",
            self.to_team_id,
        )

    @property
    def from_user(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User", self.from_user_id
        )

    @property
    def to_user(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User", self.to_user_id
        )

    @property
    def from_staff(self):
        return self._lookup(
            "app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails",
            self.from_staff_id,
            field="staff_unique_id",
        )

    @property
    def to_staff(self):
        return self._lookup(
            "app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails",
            self.to_staff_id,
            field="staff_unique_id",
        )

    @property
    def assigned_by(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User", self.assigned_by_id
        )
