from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_source_id():
    return f"CPTSRC-{generate_unique_id()}"


class ComplaintSource(BaseMaster):
    """Where a complaint ticket came from: WhatsApp, Mobile App, Web, Call Center, Admin."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_source_id,
        editable=False,
    )

    source_code = models.CharField(max_length=50, unique=True)
    source_name = models.CharField(max_length=100)

    class Meta:
        ordering = ["source_code"]
        verbose_name = "Complaint Source"
        verbose_name_plural = "Complaint Sources"

    def __str__(self):
        return self.source_name
