from django.db import models
from app.utils.base_models import BaseMaster
from enum import Enum
from .customercreation import CustomerCreation
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project



def generate_feedback_id():
    """Generate readable prefixed ID, e.g., FEED-20251103001"""
    return f"FEED-{generate_unique_id()}"


class FeedbackCategory(Enum):
    EXCELLENT = "Excellent"
    SATISFIED = "Satisfied"
    NOT_SATISFIED = "Not Satisfied"
    POOR = "Poor"


class FeedBack(BaseMaster):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_feedback_id,
        editable=False,
    )

    # Link to customer
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        related_name="feedbacks"
    )

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

    def __str__(self):
        """Readable entry with linked customer and location."""
        customer_name = self.customer.customer_name if self.customer else "Unknown"
        ward = getattr(self.customer.ward, "ward_name", "")
        zone = getattr(self.customer.zone, "zone_name", "")
        city = getattr(self.customer.city, "city_name", "")
        return f"{customer_name} - {ward or zone or city}"

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
