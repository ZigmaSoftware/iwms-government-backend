# ============================================================
# 3. trip_plan.py  (merged RoutePlan + TripDefinition)
# ============================================================
from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.zone import Zone
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
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
    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
    )
    city_id = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
    )
    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        null=True,
        blank=True,
    )
    # panchayat XOR ward mirrors Collection_point.clean() logic.
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        null=True,
        blank=True,
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
    )

    # ---- WHAT ------------------------------------------------------
    property_id = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="property_id",
    )
    sub_property_id = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="sub_property_id",
    )
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plans",
        db_column="waste_type_id",
    )
    trip_trigger_weight_kg = models.PositiveIntegerField(
        help_text="Collected weight (kg) that triggers a trip dispatch.",
    )
    max_vehicle_capacity_kg = models.PositiveIntegerField(
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
            models.Index(fields=["status", "approval_status"]),
            models.Index(fields=["display_code"]),
            models.Index(fields=["district_id", "city_id"]),
        ]
        constraints = [
            models.CheckConstraint(
                # Mirrors Collection_point: must have panchayat OR ward, not both, not neither
                check=(
                    models.Q(panchayat_id__isnull=False, ward_id__isnull=True) |
                    models.Q(panchayat_id__isnull=True,  ward_id__isnull=False)
                ),
                name="trip_plan_panchayat_xor_ward",
            )
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
