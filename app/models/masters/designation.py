from django.db import models

from app.models.masters.department import Department
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_designation_id():
    return f"DESG-{generate_unique_id()}"


class Designation(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_designation_id,
        editable=False,
    )
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="designations",
        db_column="company_id",
        null=True,
        blank=True,
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="designations",
        db_column="project_id",
        null=True,
        blank=True,
    )
    department_id = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="designations",
        db_column="department_id",
        null=True,
        blank=True,
    )
    designation_name = models.CharField(max_length=150)
    designation_group = models.CharField(max_length=80, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["designation_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company_id", "project_id", "designation_name", "department_id"],
                name="unique_designation_per_project_department",
            )
        ]

    def __str__(self):
        return self.designation_name
