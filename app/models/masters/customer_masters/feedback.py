from django.db import models
from app.utils.base_models import BaseMaster
from enum import Enum
from .customercreation import CustomerCreation
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache



def generate_feedback_id():
    """Generate readable prefixed ID, e.g., FEED-20251103001"""
    return f"FEED-{generate_unique_id()}"


class FeedbackCategory(Enum):
    EXCELLENT = "Excellent"
    SATISFIED = "Satisfied"
    NOT_SATISFIED = "Not Satisfied"
    POOR = "Poor"


class FeedBack(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_feedback_id,
        editable=False,
    )

    # Plain CustomerCreation unique_id (no DB relation).
    customer_id = models.CharField(max_length=30, db_column="customer_id", db_index=True)

    # Enum-based feedback category
    category = models.CharField(
        max_length=20,
        choices=[(tag.value, tag.value) for tag in FeedbackCategory],
        default=FeedbackCategory.SATISFIED.value
    )

    feedback_details = models.CharField(max_length=300, blank=True, null=True)

    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"
        ordering = ["-created_on"]

    @property
    def customer(self):
        return ref_cache.get(CustomerCreation, self.customer_id, "unique_id")

    def __str__(self):
        """Readable entry with linked customer and location."""
        from app.utils.hierarchy import flat_geo_display

        customer = self.customer
        customer_name = customer.customer_name if customer else "Unknown"
        location = flat_geo_display(customer)[0] if customer else ""
        return f"{customer_name} - {location or ''}"

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
