from django.db import models
from django.db.models import Q

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.user_creations.staffcreation import Staffcreation


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
    operator = models.ForeignKey(Staffcreation, on_delete=models.SET_NULL, null=True, blank=True, to_field="staff_unique_id", db_column="operator_id", related_name="unassigned_operator_pool")
    driver = models.ForeignKey(Staffcreation, on_delete=models.SET_NULL, null=True, blank=True, to_field="staff_unique_id", db_column="driver_id", related_name="unassigned_driver_pool")
    daily_trip_assignment = models.ForeignKey("app.DailyTripAssignment", on_delete=models.SET_NULL, null=True, blank=True, db_column="trip_instance_id", help_text="Daily trip assignment that triggered this pool snapshot")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "unassigned_staff_pool"
        verbose_name = "Unassigned Staff Pool"
        verbose_name_plural = "Unassigned Staff Pools"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["operator"], condition=Q(operator__isnull=False), name="uniq_unassigned_operator"),
            models.UniqueConstraint(fields=["driver"], condition=Q(driver__isnull=False), name="uniq_unassigned_driver"),
            models.CheckConstraint(check=(Q(operator__isnull=False, driver__isnull=True) | Q(operator__isnull=True, driver__isnull=False)), name="exactly_one_of_operator_or_driver"),
        ]

    def __str__(self):
        staff = self.operator_id or self.driver_id or "N/A"
        return str(staff)
