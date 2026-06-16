from django.db import models

from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staffcreation import Staffcreation


def generate_supervisor_zone_audit_id():
    return f"SZAUDIT-{generate_unique_id()}"


class SupervisorZoneAccessAudit(models.Model):
    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        default=generate_supervisor_zone_audit_id,
        editable=False,
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="project_id",
    )
    supervisor = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="staff_unique_id",
        related_name="zone_access_audits",
    )
    old_zone_ids = models.JSONField(null=True, blank=True)
    new_zone_ids = models.JSONField(default=list)
    performed_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="staff_unique_id",
        related_name="zone_access_audits_performed",
    )
    performed_role = models.CharField(max_length=50)
    remarks = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "supervisor_zone_access_audits"
        ordering = ["-created_at"]
