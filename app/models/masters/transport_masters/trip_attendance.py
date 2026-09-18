from django.db import models
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo
def generate_trip_attendance_id():
    return f"TRIPATT-{generate_unique_id()}"    

def trip_attendance_upload_path(instance, filename):
    role = "staff"
    staff_type = getattr(instance.staff, "staffusertype_id", None)
    if staff_type and staff_type.name:
        role = staff_type.name.lower()
    return f"uploads/trip_attendance/{role}/{filename}"


class TripAttendance(models.Model):
    """
    Periodic attendance capture during a running trip.
    Enforces staff presence, prevents swapping & malpractice.
    """

    class Source(models.TextChoices):
        MOBILE = "MOBILE", "Mobile App"
        VEHICLE_CAM = "VEHICLE_CAM", "Vehicle Camera"

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_trip_attendance_id,
        editable=False,
    )

    daily_trip_assignment = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        related_name="attendances",
        db_column="trip_instance_id",
        to_field="unique_id"
    )

    staff = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        related_name="trip_attendance",
        db_column="staff_id",
        to_field="staff_unique_id"
    )

    vehicle = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        related_name="trip_attendance",
        db_column="vehicle_id",
        to_field="unique_id"
    )

    # Flat geo scope block — copied from the linked DailyTripAssignment on
    # save so every attendance row is attributable to a corporation / local
    # body and can be corporation-scoped directly (see B1). Plain CharFields
    # holding the related row's `unique_id` (no DB relation/join), matching
    # the rest of the geo-hierarchy convention.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    attendance_time = models.DateTimeField()

    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)

    photo = models.ImageField(
        upload_to=trip_attendance_upload_path,
        null=True,
        blank=True
    )

    source = models.CharField(
        max_length=20,
        choices=Source.choices
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attendance_time"]
        verbose_name = "Trip Attendance"
        verbose_name_plural = "Trip Attendances"
        indexes = [
            models.Index(fields=["daily_trip_assignment", "staff"]),
            models.Index(fields=["attendance_time"]),
        ]

    def save(self, *args, **kwargs):
        # Inherit the corporation / local-body scope from the parent trip
        # assignment. `only_empty` keeps any explicitly-set geo values.
        if self.daily_trip_assignment_id and not self.corporation_id:
            copy_flat_geo(self, self.daily_trip_assignment, only_empty=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.daily_trip_assignment_id} | {self.staff_id} | {self.attendance_time}"
