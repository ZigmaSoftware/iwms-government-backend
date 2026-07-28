from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority


def generate_subcategory_id():
    return f"CPTSUB-{generate_unique_id()}"


class ComplaintSubcategory(BaseMaster):
    """Subcategories under a complaint category."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_subcategory_id,
        editable=False,
    )

    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT,
        related_name="subcategories",
    )
    subcategory_code = models.CharField(max_length=80)
    subcategory_name = models.CharField(max_length=150)
    default_priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_subcategories",
    )
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Subcategory"
        verbose_name_plural = "Complaint Subcategories"
        unique_together = ("category", "subcategory_code")

    def __str__(self):
        return self.subcategory_name
