from django.db import models
from django.db.models import Q

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils import ref_cache


def generate_unassigned_staff_pool_id():
    return f"UNASSSTAFFPOOL-{generate_unique_id()}"


class UnassignedStaffPool(BaseMaster):
    """
    Holds operators & drivers who are NOT currently assigned to any trip
    within a trip assignment.

    Used by the daily trip assignment flow to ensure
    no duplicate staff allocation.
    """

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ASSIGNED = "ASSIGNED", "Assigned"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    unique_id = models.CharField(max_length=60, primary_key=True, default=generate_unassigned_staff_pool_id, editable=False)
    # Plain id strings (no DB relation); read through the properties below.
    operator_id = models.CharField(max_length=30, null=True, blank=True, db_column="operator_id", db_index=True)  # Staffcreation.staff_unique_id
    driver_id = models.CharField(max_length=30, null=True, blank=True, db_column="driver_id", db_index=True)  # Staffcreation.staff_unique_id
    daily_trip_assignment_id = models.CharField(max_length=50, null=True, blank=True, db_column="trip_instance_id", db_index=True, help_text="unique_id of the daily trip assignment that triggered this pool snapshot")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "unassigned_staff_pool"
        verbose_name = "Unassigned Staff Pool"
        verbose_name_plural = "Unassigned Staff Pools"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["operator_id"], condition=Q(operator_id__isnull=False), name="uniq_unassigned_operator"),
            models.UniqueConstraint(fields=["driver_id"], condition=Q(driver_id__isnull=False), name="uniq_unassigned_driver"),
            models.CheckConstraint(check=(Q(operator_id__isnull=False, driver_id__isnull=True) | Q(operator_id__isnull=True, driver_id__isnull=False)), name="exactly_one_of_operator_or_driver"),
        ]

    def __str__(self):
        staff = self.operator_id or self.driver_id or "N/A"
        return str(staff)

    @property
    def operator(self):
        return ref_cache.get(Staffcreation, self.operator_id)

    @property
    def driver(self):
        return ref_cache.get(Staffcreation, self.driver_id)

    @property
    def daily_trip_assignment(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment

        return ref_cache.get(DailyTripAssignment, self.daily_trip_assignment_id, "unique_id")
