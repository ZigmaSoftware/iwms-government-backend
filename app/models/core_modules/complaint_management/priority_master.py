from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_priority_id():
    return f"CPTPRI-{generate_unique_id()}"


class ComplaintPriority(BaseMaster):
    """Priority levels: P1 Emergency, P2 High, P3 Normal, P4 Info."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_priority_id,
        editable=False,
    )

    priority_code = models.CharField(max_length=20, unique=True)
    priority_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Priority"
        verbose_name_plural = "Complaint Priorities"

    def __str__(self):
        return self.priority_name
