# api/models/login_audit.py
from django.db import models
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project



def generate_login_id():
    return f"LOGINAUDIT-{generate_unique_id()}"


class LoginAudit(models.Model):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_login_id,
        editable=False,
    )

    user_unique_id = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    username = models.CharField(max_length=150)
    password = models.CharField(max_length=150, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    success = models.BooleanField()
    reason = models.CharField(max_length=255, null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
