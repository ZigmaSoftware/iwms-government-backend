from django.db import models

from app.models.masters.department import Department
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
                fields=["designation_name", "department_id"],
                name="unique_designation_per_department",
            )
        ]

    def __str__(self):
        return self.designation_name
