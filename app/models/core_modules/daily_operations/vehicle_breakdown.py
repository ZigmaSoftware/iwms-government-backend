from django.db import models, transaction
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.hierarchy import copy_flat_geo
from app.utils import ref_cache


def _generate_vehicle_breakdown_id():
    today = timezone.localdate()
    prefix = f"VBD-{today.year}-{today.month:02d}"
    with transaction.atomic():
        existing = (
            VehicleBreakdown.objects.select_for_update()
            .filter(unique_id__startswith=f"{prefix}-")
            .values_list("unique_id", flat=True)
        )
        max_seq = 0
        for uid in existing:
            try:
                seq = int(uid.rsplit("-", 1)[-1])
                if seq > max_seq:
                    max_seq = seq
            except (ValueError, IndexError):
                pass
        return f"{prefix}-{max_seq + 1:03d}"


class VehicleBreakdown(BaseMaster):

    STATUS_REPORTED = "REPORTED"
    STATUS_REPLACEMENT_ARRANGED = "REPLACEMENT_ARRANGED"
    STATUS_REJECTED = "REJECTED"

    STATUS_CHOICES = [
        (STATUS_REPORTED, "Reported"),
        (STATUS_REPLACEMENT_ARRANGED, "Replacement Arranged"),
        (STATUS_REJECTED, "Rejected"),
    ]

    APPROVAL_PENDING = "PENDING"
    APPROVAL_APPROVED = "APPROVED"
    APPROVAL_REJECTED = "REJECTED"

    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, "Pending"),
        (APPROVAL_APPROVED, "Approved"),
        (APPROVAL_REJECTED, "Rejected"),
    ]

    BREAKDOWN_REASON_CHOICES = [
        ("FLAT_TYRE", "Flat Tyre"),
        ("ENGINE_FAILURE", "Engine Failure"),
        ("ACCIDENT", "Accident"),
        ("ELECTRICAL", "Electrical Fault"),
        ("OVERHEATING", "Overheating"),
        ("OTHER", "Other"),
    ]

    # ── Identifier ──────────────────────────────────────────────────
    unique_id = models.CharField(
        max_length=50,
        primary_key=True,
        editable=False,
        db_index=True,
    )

    # ── References ───────────────────────────────────────────────────
    # Plain id strings (no DB relation); the matching read-only properties
    # below resolve the rows through ref_cache.
    trip_assignment_id = models.CharField(
        max_length=50, unique=True, db_column="trip_assignment_id"
    )  # DailyTripAssignment.unique_id (one breakdown per trip)
    breakdown_vehicle_id = models.CharField(
        max_length=40, db_column="breakdown_vehicle_id", db_index=True
    )  # VehicleCreation.unique_id
    replacement_vehicle_id = models.CharField(
        max_length=40, db_column="replacement_vehicle_id", null=True, blank=True, db_index=True
    )  # VehicleCreation.unique_id
    # Replacement staff (assigned later by the supervisor) — Staffcreation.staff_unique_id.
    replacement_driver_id = models.CharField(
        max_length=30, db_column="replacement_driver_id", null=True, blank=True, db_index=True
    )
    replacement_operator_id = models.CharField(
        max_length=30, db_column="replacement_operator_id", null=True, blank=True, db_index=True
    )
    # AlternativeStaffTemplate created during approval.
    alt_staff_template_id = models.CharField(
        max_length=50, db_column="alt_staff_template_id", null=True, blank=True, db_index=True
    )
    # Continuation trip created on verify (mirrors TripRetripRequest.new_assignment).
    new_assignment_id = models.CharField(
        max_length=50, db_column="new_assignment_id", null=True, blank=True, db_index=True
    )

    # ── Breakdown Details ─────────────────────────────────────────────
    breakdown_time = models.TimeField(null=True, blank=True)
    breakdown_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    breakdown_lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    breakdown_location = models.CharField(max_length=255, null=True, blank=True)
    collected_weight_before_breakdown_kg = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        help_text="Weight already collected by the broken vehicle before the breakdown occurred."
    )
    breakdown_reason = models.CharField(
        max_length=20,
        choices=BREAKDOWN_REASON_CHOICES,
        default="OTHER",
    )
    breakdown_remarks = models.TextField(null=True, blank=True)

    # ── Status & Approval ─────────────────────────────────────────────
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_REPORTED,
        db_index=True,
    )
    approval_status = models.CharField(
        max_length=10,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_PENDING,
        db_index=True,
    )
    approved_by_id = models.CharField(
        max_length=30, db_column="approved_by", null=True, blank=True, db_index=True
    )  # Staffcreation.staff_unique_id
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_remarks = models.TextField(null=True, blank=True)

    # ── Flat geo scope block ──────────────────────────────────────────
    # Copied from the linked DailyTripAssignment on save so breakdowns can be
    # corporation-scoped directly instead of only through the parent (see B1).
    # Plain CharFields holding the related row's unique_id (no DB
    # relation/join), matching the rest of the geo-hierarchy convention.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "approval_status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.unique_id:
            self.unique_id = _generate_vehicle_breakdown_id()
        # Inherit corporation / local-body scope from the parent trip
        # assignment on first write. `only_empty` preserves explicit values.
        if self.trip_assignment_id and not self.corporation_id:
            assignment = self.trip_assignment
            if assignment is not None:
                copy_flat_geo(self, assignment, only_empty=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id

    @property
    def trip_assignment(self):
        return ref_cache.get(DailyTripAssignment, self.trip_assignment_id, "unique_id")

    @property
    def breakdown_vehicle(self):
        return ref_cache.get(VehicleCreation, self.breakdown_vehicle_id)

    @property
    def replacement_vehicle(self):
        return ref_cache.get(VehicleCreation, self.replacement_vehicle_id)

    @property
    def replacement_driver(self):
        return ref_cache.get(Staffcreation, self.replacement_driver_id)

    @property
    def replacement_operator(self):
        return ref_cache.get(Staffcreation, self.replacement_operator_id)

    @property
    def alt_staff_template(self):
        return ref_cache.get(AlternativeStaffTemplate, self.alt_staff_template_id)

    @property
    def new_assignment(self):
        return ref_cache.get(DailyTripAssignment, self.new_assignment_id, "unique_id")

    @property
    def approved_by(self):
        return ref_cache.get(Staffcreation, self.approved_by_id)

    @property
    def photos(self):
        """Photos of this breakdown (VehicleBreakdownPhoto.breakdown_id is a
        plain unique_id); replaces the reverse FK accessor."""
        return VehicleBreakdownPhoto.objects.filter(breakdown_id=self.unique_id)


def vehicle_breakdown_photo_upload_path(instance, filename):
    return f"uploads/vehicle_breakdown/{instance.breakdown_id}/{filename}"


class VehicleBreakdownPhoto(models.Model):
    breakdown_id = models.CharField(
        max_length=50, db_column="breakdown_id", db_index=True
    )  # VehicleBreakdown.unique_id
    photo = models.ImageField(upload_to=vehicle_breakdown_photo_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.breakdown_id} photo #{self.pk}"

    @property
    def breakdown(self):
        return ref_cache.get(VehicleBreakdown, self.breakdown_id)
