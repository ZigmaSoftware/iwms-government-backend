from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.user_creations.staffcreation import Staffcreation


def generate_supervisor_zone_map_id():
    return f"SUPZONE-{generate_unique_id()}"


class SupervisorZoneMap(BaseMaster):
    STATUS_ACTIVE = "ACTIVE"
    STATUS_INACTIVE = "INACTIVE"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    unique_id = models.CharField(max_length=50, primary_key=True, default=generate_supervisor_zone_map_id, editable=False)
    supervisor_id = models.ForeignKey(Staffcreation, on_delete=models.PROTECT, to_field="staff_unique_id", db_column="supervisor_id", related_name="zone_assignments")
    district_id = models.ForeignKey(District, on_delete=models.SET_NULL, to_field="unique_id", db_column="district_id", null=True, blank=True)
    city_id = models.ForeignKey(City, on_delete=models.SET_NULL, to_field="unique_id", db_column="city_id", null=True, blank=True)
    zone_ids = models.JSONField(default=list, help_text="List of zone unique IDs the supervisor is authorized to operate in")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supervisor_zone_maps"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["supervisor_id", "status"]),
            models.Index(fields=["district_id"]),
            models.Index(fields=["city_id"]),
        ]

    def __str__(self):
        return f"{self.supervisor_id_id} - {self.zone_ids}"
