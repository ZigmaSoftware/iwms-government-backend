# ============================================================
# 3. trip_plan.py  (merged RoutePlan + TripDefinition)
# ============================================================
from django.db import models
from django.db.models import Max
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.masters.ward import Ward
from app.utils import ref_cache


def generate_trip_plan_id():
    return f"TPLAN-{generate_unique_id()}"


class TripPlan(BaseMaster):
    """Single source of truth for route + trip configuration."""

    CACHE_SCOPES = ("trip_plan_list", "trip_plan_detail")
    CASCADE_SOFT_DELETE = ("plan_collection_points", "daily_trip_assignments")

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
    # state_id/district_id/area_type_id/corporation_id/municipality_id/
    # town_panchayat_id/panchayat_union_id/panchayat_id are plain CharFields
    # holding the related row's `unique_id` (no DB relation/join) — matching
    # the rest of the geo-hierarchy (Ward, CustomerCreation, Corporation/
    # District/.../Panchayat, ...).
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    # A trip plan can span multiple wards within its selected local body
    # (e.g. one corporation route covering several wards in a single run).
    # Ward unique_ids covered by this trip plan (no DB relation).
    ward_ids = models.JSONField(
        default=list, blank=True, help_text="Ward unique_ids covered by this trip plan."
    )
    # ---- WHO -------------------------------------------------------
    # Plain unique_ids (no DB relation); the `staff_template` / `vehicle` /
    # `supervisor` properties below resolve them.
    staff_template_id = models.CharField(max_length=20, db_column="staff_template_id", db_index=True)
    vehicle_id = models.CharField(max_length=40, db_column="vehicle_id", db_index=True)
    supervisor_id = models.CharField(
        max_length=30, null=True, blank=True, db_column="supervisor_id", db_index=True
    )

    # ---- WHAT ------------------------------------------------------
    # Supports multiple waste types per trip plan (e.g. household + bulk)
    waste_type_ids = models.JSONField(
        default=list, blank=True, help_text="WasteType unique_ids handled by this trip plan."
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
            models.Index(fields=["district_id"]),
        ]

    # ---- plain-reference lookups -----------------------------------
    def _lookup(self, model, **filters):
        ((field, value),) = filters.items()
        return ref_cache.get(model, value, field)

    @property
    def staff_template(self):
        if not self.staff_template_id:
            return None
        return self._lookup(StaffTemplate, unique_id=self.staff_template_id)

    @property
    def vehicle(self):
        if not self.vehicle_id:
            return None
        return self._lookup(VehicleCreation, unique_id=self.vehicle_id)

    @property
    def supervisor(self):
        if not self.supervisor_id:
            return None
        return self._lookup(Staffcreation, staff_unique_id=self.supervisor_id)

    @property
    def plan_collection_points(self):
        """TripPlanCollectionPoint rows for this plan (plain trip_plan_id);
        replaces the reverse FK accessor CASCADE_SOFT_DELETE expects."""
        from app.models.core_modules.schedule_setup.trip_plan_collection_point import (
            TripPlanCollectionPoint,
        )

        return TripPlanCollectionPoint.objects.filter(trip_plan_id=self.unique_id)

    @property
    def daily_trip_assignments(self):
        """DailyTripAssignment rows generated from this plan (plain
        trip_plan_id); replaces the reverse FK accessor."""
        from app.models.core_modules.daily_operations.daily_trip_assignment import (
            DailyTripAssignment,
        )

        return DailyTripAssignment.objects.filter(trip_plan_id=self.unique_id)

    @property
    def wards(self):
        """Ward QuerySet for `ward_ids`."""
        return Ward.objects.filter(unique_id__in=self.ward_ids or [])

    @property
    def waste_types(self):
        """WasteType QuerySet for `waste_type_ids`."""
        return WasteType.objects.filter(unique_id__in=self.waste_type_ids or [])

    def _generate_display_code(self):
        driver_name = "DRV"
        template = self.staff_template
        if template and template.driver:
            driver_name = template.driver.employee_name[:6].upper().replace(" ", "")
        vehicle_no = "VEH"
        if self.vehicle:
            vehicle_no = self.vehicle.vehicle_no.upper().replace(" ", "")

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
