from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.utils.hierarchy import copy_flat_geo


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

    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_assignments",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_assignments",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_assignments",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_assignments",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_assignments",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_assignments",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_assignments",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_assignments",
        to_field="unique_id",
        db_column="panchayat_id",
    )

    # ------------------------------------------------------------------
    # WASTE TYPE
    # ------------------------------------------------------------------

    # Waste types collected on this daily trip (inherited from the Trip Plan;
    # can be narrowed per-trip).
    waste_types = models.ManyToManyField(
        WasteType,
        related_name="daily_trip_assignments_multi",
        blank=True,
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
            models.Index(fields=["district", "trip_date"]),
        ]

    # ------------------------------------------------------------------
    # UNIQUE_ID GENERATION
    # ------------------------------------------------------------------

    def save(self, *args, **kwargs):
        if self.trip_plan_id:
            self.staff_template_id = self.staff_template_id or self.trip_plan_id.staff_template_id
            self.vehicle_id = self.vehicle_id or self.trip_plan_id.vehicle_id
            copy_flat_geo(self, self.trip_plan_id, only_empty=True)
            self.scheduled_time = self.scheduled_time or self.trip_plan_id.scheduled_time
        if not self.unique_id:
            self.unique_id = _generate_trip_assignment_unique_id()
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new and self.trip_plan_id and not self.waste_types.exists():
            self.waste_types.set(self.trip_plan_id.waste_types.all())

    def __str__(self):
        return self.unique_id

    def mark_completed_if_all_cps_collected(self):
        children = self.trip_collection_points.filter(is_deleted=False)
        if not children.exists():
            return False
        # A missed stop is operationally resolved for the day but contributes
        # zero weight. "Skipped" / collect-later remains unresolved.
        if children.exclude(status__in=["Collected", "Missed"]).exists():
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
