from django.db import models

from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_department_id():
    return f"DEPT-{generate_unique_id()}"


class Department(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_department_id,
        editable=False,
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="departments",
        db_column="company_id",
        null=True,
        blank=True,
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="departments",
        db_column="project_id",
        null=True,
        blank=True,
    )
    department_name = models.CharField(max_length=150)
    department_code = models.CharField(max_length=30)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["department_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "project_id", "department_code"],
                name="unique_department_code_per_project",
            )
        ]

    def __str__(self):
        return self.department_name
