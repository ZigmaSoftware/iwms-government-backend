from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.user_creations.waste_collection_bluetooth import WasteType


def _generate_trip_assignment_unique_id():
    """
    Generates TRIP-YYYY-MM-NNN, where NNN is sequential per month.
    Inline import avoids circular-import at module load time.
    """
    today = timezone.localdate()
    prefix = f"TRIP-{today.year}-{today.month:02d}"
    count = DailyTripAssignment.objects.filter(
        unique_id__startswith=f"{prefix}-",
    ).count()
    return f"{prefix}-{count + 1:03d}"


class DailyTripAssignment(BaseMaster):

    STATUS_SCHEDULED = "Scheduled"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    APPROVAL_PENDING = "Pending"
    APPROVAL_APPROVED = "Approved"
    APPROVAL_REJECTED = "Rejected"

    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, "Pending"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    ]

    # ------------------------------------------------------------------
    # IDENTIFIER
    # ------------------------------------------------------------------

    unique_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
    )

    # ------------------------------------------------------------------
    # TENANCY
    # ------------------------------------------------------------------



    # ------------------------------------------------------------------
    # TRIP PLAN & STAFF
    # ------------------------------------------------------------------

    trip_plan_id = models.ForeignKey(
        TripPlan,
        on_delete=models.PROTECT,
        db_column="trip_plan_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    staff_template_id = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        db_column="staff_template_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    alt_staff_template_id = models.ForeignKey(
        AlternativeStaffTemplate,
        on_delete=models.PROTECT,
        db_column="alt_staff_template_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------
    # LOCATION
    # ------------------------------------------------------------------

    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        db_column="panchayat_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        db_column="ward_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------
    # WASTE TYPE
    # ------------------------------------------------------------------

    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        db_column="waste_type_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
    )

    # Multiple waste types for household collection stops on this trip
    household_waste_type_ids = models.ManyToManyField(
        WasteType,
        related_name="household_trip_assignments",
        blank=True,
    )

    # ------------------------------------------------------------------
    # VEHICLE (explicit for operator-mobile flow)
    # ------------------------------------------------------------------

    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="daily_trip_assignments",
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------
    # SCHEDULING
    # ------------------------------------------------------------------

    trip_date = models.DateField()
    scheduled_time = models.TimeField()
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)

    # ------------------------------------------------------------------
    # STATUS & APPROVAL
    # ------------------------------------------------------------------

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
        db_index=True,
    )

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_PENDING,
        db_index=True,
    )

    remarks = models.TextField(null=True, blank=True)

    # ------------------------------------------------------------------
    # AUDIT
    # ------------------------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ------------------------------------------------------------------
    # META
    # ------------------------------------------------------------------

    class Meta:
        ordering = ["-trip_date", "-scheduled_time"]
        indexes = [
            models.Index(fields=["trip_date", "status"]),
            models.Index(fields=["trip_plan_id", "trip_date"]),
            models.Index(fields=["panchayat_id", "trip_date"]),
            models.Index(fields=["ward_id", "trip_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(panchayat_id__isnull=False, ward_id__isnull=True) |
                    models.Q(panchayat_id__isnull=True, ward_id__isnull=False)
                ),
                name="daily_trip_assignment_panchayat_xor_ward",
            )
        ]

    # ------------------------------------------------------------------
    # UNIQUE_ID GENERATION
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        if self.trip_plan_id:
            self.staff_template_id = self.staff_template_id or self.trip_plan_id.staff_template_id
            self.vehicle_id = self.vehicle_id or self.trip_plan_id.vehicle_id
            self.waste_type_id = self.waste_type_id or self.trip_plan_id.waste_type_id
            self.panchayat_id = self.panchayat_id or self.trip_plan_id.panchayat_id
            self.ward_id = self.ward_id or self.trip_plan_id.ward_id
            self.scheduled_time = self.scheduled_time or self.trip_plan_id.scheduled_time
        if not self.unique_id:
            self.unique_id = _generate_trip_assignment_unique_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id

    def mark_completed_if_all_cps_collected(self):
        children = self.trip_collection_points.filter(is_deleted=False)
        if not children.exists():
            return False
        if children.filter(is_collected=False).exists():
            return False
        if self.status == self.STATUS_COMPLETED:
            return True

        update_fields = ["status", "updated_at"]
        self.status = self.STATUS_COMPLETED
        if not self.actual_end_time:
            self.actual_end_time = timezone.localtime().time()
            update_fields.append("actual_end_time")
        self.save(update_fields=update_fields)
        return True
