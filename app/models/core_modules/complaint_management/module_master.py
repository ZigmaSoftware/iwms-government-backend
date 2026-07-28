from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_module_id():
    return f"CPTMOD-{generate_unique_id()}"


class ComplaintModule(BaseMaster):
    """Top-level business module a complaint category belongs to (Assets, Transport, ...)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_module_id,
        editable=False,
    )

    module_code = models.CharField(max_length=80, unique=True)
    module_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Module"
        verbose_name_plural = "Complaint Modules"

    def __str__(self):
        return self.module_name
