from django.db import models
from django.utils import timezone
from app.utils.comfun import generate_unique_id


def generate_audit_id():
    return f"AUDIT-{generate_unique_id()}"


class CommonAudit(models.Model):

    uuid = models.CharField(
        max_length=50,
        primary_key=True,
        default=generate_audit_id,
        editable=False
    )

    module_name = models.CharField(max_length=150)
    endpoint_name = models.CharField(max_length=150)
    method = models.CharField(max_length=10)  

    previous_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)

    object_id = models.CharField(max_length=150, null=True, blank=True)

    createdBy = models.CharField(max_length=150, null=True, blank=True)
    createdAt = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "common_audit"
        ordering = ["-createdAt"]

    def __str__(self):
        return self.uuid