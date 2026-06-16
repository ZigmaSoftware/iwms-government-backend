from django.db import models

from .company import Company
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_project_id():
    return f"PROJ-{generate_unique_id()}"


class Project(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_project_id,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="projects",
        to_field="unique_id",
        db_column="company_id",
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    gps_api_url = models.URLField(max_length=500, blank=True, null=True)
    weighment_api_url = models.URLField(max_length=500, blank=True, null=True)
    attendance_api_url = models.URLField(max_length=500, blank=True, null=True)
    attendance_api_key = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.company_id.name})"

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
