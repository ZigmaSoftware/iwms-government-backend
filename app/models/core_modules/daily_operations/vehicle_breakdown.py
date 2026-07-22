from django.db import models, transaction
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.utils.hierarchy import copy_flat_geo


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

    # ── Trip Reference ───────────────────────────────────────────────
    trip_assignment_id = models.OneToOneField(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="trip_assignment_id",
        related_name="vehicle_breakdown",
    )

    # ── Vehicles ─────────────────────────────────────────────────────
    breakdown_vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="breakdown_vehicle_id",
        related_name="vehicle_breakdowns_as_broken",
    )
    replacement_vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        to_field="unique_id",
        db_column="replacement_vehicle_id",
        related_name="vehicle_breakdowns_as_replacement",
    )

    # ── Replacement Staff ─────────────────────────────────────────────
    replacement_driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        db_column="replacement_driver_id",
        related_name="vehicle_breakdowns_as_driver",
    )
    replacement_operator_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        db_column="replacement_operator_id",
        related_name="vehicle_breakdowns_as_operator",
    )

    # ── Created AlternativeStaffTemplate (set during approval) ───────
    alt_staff_template_id = models.ForeignKey(
        AlternativeStaffTemplate,
        on_delete=models.SET_NULL,
        to_field="unique_id",
        db_column="alt_staff_template_id",
        related_name="vehicle_breakdown",
        null=True,
        blank=True,
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
    approved_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        to_field="staff_unique_id",
        db_column="approved_by",
        related_name="vehicle_breakdown_approvals",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_remarks = models.TextField(null=True, blank=True)

    # ── Flat geo scope block ──────────────────────────────────────────
    # Copied from the linked DailyTripAssignment on save so breakdowns can be
    # corporation-scoped directly instead of only through the parent (see B1).
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_breakdowns",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_breakdowns",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_breakdowns",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_breakdowns",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_breakdowns",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_breakdowns",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_breakdowns",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_breakdowns",
        to_field="unique_id",
        db_column="panchayat_id",
    )

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
        if self.trip_assignment_id_id and not self.corporation_id:
            copy_flat_geo(self, self.trip_assignment_id, only_empty=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id
