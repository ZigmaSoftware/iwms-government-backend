from django.db import models

from app.models.masters.corporation import Corporation
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
    # Departments belong to a Corporation (this is a corporation-level
    # government product). Nullable so pre-existing rows and non-corporation
    # flows keep working; staff forms filter department options by corporation.
    corporation_id = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departments",
        db_column="corporation_id",
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
                fields=["department_code"],
                name="unique_department_code",
            )
        ]

    def __str__(self):
        return self.department_name
