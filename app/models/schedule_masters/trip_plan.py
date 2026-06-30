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
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.models.user_creations.waste_collection_bluetooth import WasteType


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
    location_node = models.ForeignKey(
        "app.HierarchyNode",
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="location_node_id",
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
    property_id = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="property_id",
        null=True,
        blank=True,
    )
    sub_property_id = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="sub_property_id",
        null=True,
        blank=True,
    )
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
            models.Index(fields=["location_node"]),
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
