from django.db import models

from app.utils.base_models import BaseMaster
from app.models.user_creations.waste_collection_bluetooth import generate_waste_type_id


class WasteType(BaseMaster, models.Model):
    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_waste_type_id,
        editable=False,
    )
    waste_type_name = models.CharField(max_length=255)
    is_deleted = models.BooleanField(default=False)

    # Public grievance routing: lets a waste type drive team/priority/SLA
    # assignment directly, instead of going through ComplaintCategory.
    default_team = models.ForeignKey(
        "app.ComplaintTeam",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_waste_types",
    )
    default_priority = models.ForeignKey(
        "app.ComplaintPriority",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_for_waste_types",
    )
    assign_within_minutes = models.IntegerField(null=True, blank=True)
    resolve_within_minutes = models.IntegerField(null=True, blank=True)
    working_hours_only = models.BooleanField(default=False)
