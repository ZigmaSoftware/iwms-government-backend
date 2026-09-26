from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


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
    department_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    lead_staff_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    escalates_to_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    escalation_level = models.IntegerField(default=1)
    is_field_team = models.BooleanField(default=False)

    class Meta:
        ordering = ["team_code"]
        verbose_name = "Complaint Team"
        verbose_name_plural = "Complaint Teams"

    def __str__(self):
        return self.team_name

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def department(self):
        return self._lookup(
            "app.models.masters.department.Department", self.department_id
        )

    @property
    def lead_staff(self):
        return self._lookup(
            "app.models.superadmin.staff_management.staffcreation.StaffcreationOfficeDetails",
            self.lead_staff_id,
            field="staff_unique_id",
        )

    @property
    def escalates_to(self):
        if not self.escalates_to_id:
            return None
        return type(self).objects.filter(unique_id=self.escalates_to_id).first()

    @property
    def escalation_sources(self):
        return type(self).objects.filter(escalates_to_id=self.unique_id)

    @property
    def assigned_tickets(self):
        from app.models.core_modules.complaint_management.ticket import ComplaintTicket

        return ComplaintTicket.objects.filter(assigned_team_id=self.unique_id)
