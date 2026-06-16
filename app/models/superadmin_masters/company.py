from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_company_id():
    return f"CMP-{generate_unique_id()}"


class Company(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_company_id,
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    company_logo = models.ImageField(
        upload_to="company_logos/",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
