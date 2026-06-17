from django.db import models

from app.utils.comfun import generate_unique_id
from app.models.user_creations.staffcreation import Staffcreation


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
    performed_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        to_field="staff_unique_id",
        related_name="staff_template_audit_logs",
    )
    performed_role = models.CharField(max_length=15, choices=PerformedRole.choices)
    change_remarks = models.TextField(null=True, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "staff_template_audit_logs"
        ordering = ["-performed_at"]
