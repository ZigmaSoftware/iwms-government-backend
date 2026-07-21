from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_language_id():
    return f"CPTLANG-{generate_unique_id()}"


class ComplaintLanguage(BaseMaster):
    """Citizen-facing languages: en, hi, ta, te."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_language_id,
        editable=False,
    )

    language_code = models.CharField(max_length=20, unique=True)
    language_name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["language_code"]
        verbose_name = "Complaint Language"
        verbose_name_plural = "Complaint Languages"

    def __str__(self):
        return self.language_name
