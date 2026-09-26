from django.db import models

from app.models.masters.department import Department
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_designation_id():
    return f"DESG-{generate_unique_id()}"


class Designation(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_designation_id,
        editable=False,
    )
    # Plain Department unique_id (no DB relation).
    department_id = models.CharField(
        max_length=30, null=True, blank=True, db_column="department_id", db_index=True
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
                fields=["designation_name", "department_id"],
                name="unique_designation_per_department",
            )
        ]

    @property
    def department(self):
        if not self.department_id:
            return None
        return ref_cache.get(Department, self.department_id)

    def __str__(self):
        return self.designation_name
