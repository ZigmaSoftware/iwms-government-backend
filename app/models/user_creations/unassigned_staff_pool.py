from django.db import models
from django.db.models import Q

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward
from app.models.user_creations.staffcreation import Staffcreation


def generate_unassigned_staff_pool_id():
    return f"UNASSSTAFFPOOL-{generate_unique_id()}"


class UnassignedStaffPool(BaseMaster):
    """
    Holds operators & drivers who are NOT currently assigned to any trip
    within a specific zone/ward.

    Used by the daily trip assignment flow to ensure
    no cross-zone staff allocation.
    """

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ASSIGNED = "ASSIGNED", "Assigned"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    unique_id = models.CharField(max_length=60, primary_key=True, default=generate_unassigned_staff_pool_id, editable=False)
    operator = models.ForeignKey(Staffcreation, on_delete=models.SET_NULL, null=True, blank=True, to_field="staff_unique_id", db_column="operator_id", related_name="unassigned_operator_pool")
    driver = models.ForeignKey(Staffcreation, on_delete=models.SET_NULL, null=True, blank=True, to_field="staff_unique_id", db_column="driver_id", related_name="unassigned_driver_pool")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, to_field="unique_id", db_column="zone_id")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, to_field="unique_id", db_column="ward_id")
    daily_trip_assignment = models.ForeignKey("app.DailyTripAssignment", on_delete=models.SET_NULL, null=True, blank=True, db_column="trip_instance_id", help_text="Daily trip assignment that triggered this pool snapshot")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "unassigned_staff_pool"
        verbose_name = "Unassigned Staff Pool"
        verbose_name_plural = "Unassigned Staff Pools"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["operator", "zone", "ward"], condition=Q(operator__isnull=False), name="uniq_operator_zone_ward"),
            models.UniqueConstraint(fields=["driver", "zone", "ward"], condition=Q(driver__isnull=False), name="uniq_driver_zone_ward"),
            models.CheckConstraint(check=(Q(operator__isnull=False, driver__isnull=True) | Q(operator__isnull=True, driver__isnull=False)), name="exactly_one_of_operator_or_driver"),
        ]

    def __str__(self):
        staff = self.operator_id or self.driver_id or "N/A"
        return f"{staff} - {self.zone_id}"
