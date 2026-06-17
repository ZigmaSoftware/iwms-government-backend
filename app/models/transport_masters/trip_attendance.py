from django.db import models
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.user_creations.staffcreation import Staffcreation
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.utils.comfun import generate_unique_id
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

    def __str__(self):
        return f"{self.daily_trip_assignment_id} | {self.staff_id} | {self.attendance_time}"
