from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_status_id():
    return f"CPTSTAT-{generate_unique_id()}"


class ComplaintStatus(BaseMaster):
    """Ticket lifecycle statuses: SUBMITTED, ASSIGNED, IN_PROGRESS, RESOLVED, ..."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_status_id,
        editable=False,
    )

    status_code = models.CharField(max_length=50, unique=True)
    status_name = models.CharField(max_length=100)
    is_final = models.BooleanField(default=False)
    allow_reopen = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Status"
        verbose_name_plural = "Complaint Statuses"

    def __str__(self):
        return self.status_name
