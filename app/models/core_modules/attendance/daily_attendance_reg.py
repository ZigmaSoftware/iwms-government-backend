from django.db import models

from app.utils.comfun import generate_unique_id


def generate_daily_attendance_reg_id():
    return f"DAR-{generate_unique_id()}"


class DailyAttendanceReg(models.Model):
    """A face-recognition attendance punch mapped directly to staff."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_daily_attendance_reg_id,
        editable=False,
    )
    staff_id = models.CharField(
        max_length=30,
        db_column="staff_id",
        db_index=True,
    )
    emp_id = models.CharField(max_length=10)
    emp_id_raw = models.CharField(max_length=50, null=True, blank=True)
    name = models.CharField(max_length=100)
    records = models.DateTimeField()
    captured_image_path = models.CharField(max_length=255)
    similarity_score = models.FloatField()
    latitude = models.CharField(max_length=50)
    longitude = models.CharField(max_length=50)
    recognition_date = models.DateField()
    recognition_time = models.TimeField()
    punch_type = models.CharField(max_length=3, default="IN")
    worked_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "app_trip_attendance"
        ordering = ["-records"]
        indexes = [
            models.Index(fields=["emp_id"]),
            models.Index(fields=["staff_id"]),
            models.Index(fields=["recognition_date", "punch_type"]),
        ]
