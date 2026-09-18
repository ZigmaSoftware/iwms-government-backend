from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_department_id():
    return f"DEPT-{generate_unique_id()}"


class Department(BaseMaster):
    CACHE_SCOPES = ("department_list", "department_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_department_id,
        editable=False,
    )
    # Departments belong to a Corporation (this is a corporation-level
    # government product). Nullable so pre-existing rows and non-corporation
    # flows keep working; staff forms filter department options by corporation.
    # Plain CharField holding Corporation.unique_id (no DB relation/join) —
    # matches the rest of the geo-hierarchy refactor's convention.
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
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
