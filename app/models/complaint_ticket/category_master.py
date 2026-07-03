from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.complaint_ticket.priority_master import ComplaintPriority
from app.models.complaint_ticket.team_master import ComplaintTeam


def generate_category_id():
    return f"CPTCAT-{generate_unique_id()}"


class ComplaintCategory(BaseMaster):
    """Top-level complaint categories (Missed Pickup, Change Address, ...)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_category_id,
        editable=False,
    )

    category_code = models.CharField(max_length=80, unique=True)
    category_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)

    default_priority = models.ForeignKey(
        ComplaintPriority,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="default_for_categories",
    )
    default_team = models.ForeignKey(
        ComplaintTeam,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_categories",
    )

    requires_location = models.BooleanField(default=True)
    requires_media = models.BooleanField(default=False)
    requires_address_change_detail = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "Complaint Category"
        verbose_name_plural = "Complaint Categories"

    def __str__(self):
        return self.category_name
