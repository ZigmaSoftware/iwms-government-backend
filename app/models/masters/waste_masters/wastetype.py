from django.db import models

from app.utils.base_models import BaseMaster
from app.models.waste_collection_bluetooth.waste_collection_bluetooth import generate_waste_type_id
from app.utils import ref_cache


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
    # Plain ComplaintTeam / ComplaintPriority unique_ids (no DB relation).
    default_team_id = models.CharField(
        max_length=30, null=True, blank=True, db_column="default_team_id", db_index=True
    )
    default_priority_id = models.CharField(
        max_length=30, null=True, blank=True, db_column="default_priority_id", db_index=True
    )
    assign_within_minutes = models.IntegerField(null=True, blank=True)
    resolve_within_minutes = models.IntegerField(null=True, blank=True)
    working_hours_only = models.BooleanField(default=False)

    @property
    def default_team(self):
        from app.models.core_modules.complaint_management.team_master import ComplaintTeam

        if not self.default_team_id:
            return None
        return ref_cache.get(ComplaintTeam, self.default_team_id)

    @property
    def default_priority(self):
        from app.models.core_modules.complaint_management.priority_master import ComplaintPriority

        if not self.default_priority_id:
            return None
        return ref_cache.get(ComplaintPriority, self.default_priority_id)
