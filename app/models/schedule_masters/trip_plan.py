# ============================================================
# 3. trip_plan.py  (merged RoutePlan + TripDefinition)
# ============================================================
from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.schedule_masters.collection_point import Collection_point
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.assets.wastetype import WasteType
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat


def generate_trip_plan_id():
    return f"TPLAN-{generate_unique_id()}"


class TripPlan(BaseMaster):
    """Single source of truth for route + trip configuration."""

    COLLECTION_TYPE_BIN = "bin_collection"
    COLLECTION_TYPE_HOUSEHOLD = "household_collection"
    COLLECTION_TYPE_BULK = "bulk_waste_collection"
    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_BIN, "Secondary Collection Point"),
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
        (COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
    ]

    class ApprovalStatus(models.TextChoices):
        PENDING  = "PENDING",  "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Status(models.TextChoices):
        ACTIVE   = "ACTIVE",   "Active"
        INACTIVE = "INACTIVE", "Inactive"

    # ---- identifier ------------------------------------------------
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_trip_plan_id,
        editable=False,
    )
    display_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
        help_text="e.g. RAVI-TN01AB1234-01",
    )

    # ---- tenancy ---------------------------------------------------

    # ---- WHERE -----------------------------------------------------
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plans",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plans",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plans",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plans",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plans",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plans",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plans",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plans",
        to_field="unique_id",
        db_column="panchayat_id",
    )
    # ---- WHO -------------------------------------------------------
    staff_template_id = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="staff_template_id",
    )
    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
    )
    supervisor_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        to_field="staff_unique_id",
        related_name="trip_plans",
        null=True,
        blank=True,
    )

    # ---- WHAT ------------------------------------------------------
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="waste_type_id",
        null=True,
        blank=True,
    )
    # Supports multiple waste types per trip plan (e.g. household + bulk)
    waste_types = models.ManyToManyField(
        WasteType,
        related_name="trip_plans_multi",
        blank=True,
        help_text="Multiple waste types handled by this trip plan.",
    )
    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_BIN,
        db_index=True,
        help_text="One Trip Plan can generate only one category of daily work.",
    )
    trip_trigger_weight_kg = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Collected weight (kg) that triggers a trip dispatch.",
    )
    max_vehicle_capacity_kg = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Hard ceiling for vehicle load (kg).",
    )

    # ---- WHEN -------------------------------------------------------
    scheduled_time = models.TimeField(
        help_text="Default departure time for trips generated from this plan.",
    )
    # ---- AUTO-ASSIGN ------------------------------------------------
    is_auto_assign = models.BooleanField(
        default=False,
        help_text="If true, DailyTripAssignment will be auto-generated from this plan.",
        db_index=True,
    )
    # repeat_days: list of integers 0-6 where Monday=0. If null or empty, no repeats.
    repeat_days = models.JSONField(
        null=True,
        blank=True,
        help_text="JSON list of weekdays (0=Monday..6=Sunday) when auto-assign runs.",
    )

    # ---- workflow --------------------------------------------------
    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["collection_type"]),
            models.Index(fields=["status", "approval_status"]),
            models.Index(fields=["display_code"]),
            models.Index(fields=["district"]),
        ]

    def _generate_display_code(self):
        driver_name = "DRV"
        if self.staff_template_id and self.staff_template_id.driver_id:
            driver_name = (
                self.staff_template_id.driver_id.employee_name[:6]
                .upper().replace(" ", "")
            )
        vehicle_no = "VEH"
        if self.vehicle_id:
            vehicle_no = self.vehicle_id.vehicle_no.upper().replace(" ", "")

        base = f"{driver_name}-{vehicle_no}"
        last = (
            TripPlan.objects
            .filter(display_code__startswith=base)
            .aggregate(max_code=Max("display_code"))
            .get("max_code")
        )
        seq = 0
        if last:
            try:
                seq = int(last.split("-")[-1])
            except ValueError:
                pass
        return f"{base}-{seq + 1:02d}"

    def save(self, *args, **kwargs):
        if not self.display_code:
            self.display_code = self._generate_display_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.display_code or self.unique_id
