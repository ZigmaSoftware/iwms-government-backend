from django.db import models

from app.utils.comfun import generate_unique_id
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils import ref_cache


def generate_staff_template_audit_id():
    return f"STAUDIT-{generate_unique_id()}"


class StaffTemplateAuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Create"
        MODIFY = "MODIFY", "Modify"
        DELETE = "DELETE", "Delete"

    class PerformedRole(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        SUPERVISOR = "SUPERVISOR", "Supervisor"

    class EntityType(models.TextChoices):
        STAFF_TEMPLATE = "STAFF_TEMPLATE", "Staff Template"
        ALT_STAFF_TEMPLATE = "ALT_STAFF_TEMPLATE", "Alternative Staff Template"

    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        default=generate_staff_template_audit_id,
        editable=False,
    )
    entity_type = models.CharField(max_length=30, choices=EntityType.choices)
    entity_id = models.CharField(max_length=60)
    action = models.CharField(max_length=10, choices=Action.choices)
    # Staffcreation.staff_unique_id (plain string, no DB relation).
    performed_by_id = models.CharField(
        max_length=30, db_column="performed_by_id", null=True, blank=True, db_index=True
    )
    performed_role = models.CharField(max_length=15, choices=PerformedRole.choices)
    change_remarks = models.TextField(null=True, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_template_audit_logs"
        ordering = ["-performed_at"]

    @property
    def performed_by(self):
        return ref_cache.get(Staffcreation, self.performed_by_id)
