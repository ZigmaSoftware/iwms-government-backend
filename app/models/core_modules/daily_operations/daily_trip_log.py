from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from app.utils.plain_ref import ref_id
from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.masters.waste_masters.wastetype import WasteType
from app.utils.base_models import Account, BaseMaster
from app.utils.hierarchy import copy_flat_geo
from app.utils import ref_cache


def _generate_daily_trip_log_unique_id():
    today = timezone.localdate()
    prefix = f"DTL-{today.year}-{today.month:02d}"
    # Use the highest existing suffix + 1 (not a plain count, which collides once
    # any log for the month has been deleted) and guarantee uniqueness.
    existing = DailyTripLog.objects.filter(
        unique_id__startswith=f"{prefix}-",
    ).values_list("unique_id", flat=True)
    max_n = 0
    for uid in existing:
        try:
            max_n = max(max_n, int(uid.rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    candidate = max_n + 1
    while DailyTripLog.objects.filter(unique_id=f"{prefix}-{candidate:03d}").exists():
        candidate += 1
    return f"{prefix}-{candidate:03d}"


class DailyTripLog(BaseMaster):
    LOG_STATUS_DRAFT = "Draft"
    LOG_STATUS_SUBMITTED = "Submitted"
    LOG_STATUS_VERIFIED = "Verified"

    LOG_STATUS_CHOICES = [
        (LOG_STATUS_DRAFT, "Draft"),
        (LOG_STATUS_SUBMITTED, "Submitted"),
        (LOG_STATUS_VERIFIED, "Verified"),
    ]

    unique_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
    )

    # Plain unique_id references (no DB relation); properties below resolve
    # them. One log per assignment, hence unique.
    trip_assignment_id = models.CharField(max_length=50, db_column="trip_assignment_id", unique=True)

    staff_template_id = models.CharField(max_length=20, db_column="staff_template_id", null=True, blank=True, db_index=True)
    alt_staff_template_id = models.CharField(max_length=50, db_column="alt_staff_template_id", null=True, blank=True, db_index=True)

    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    collection_point_id = models.CharField(max_length=30, db_column="collection_point_id", null=True, blank=True)
    # Waste types collected on this trip (inherited from the Daily Trip Assignment).
    # WasteType / extra operator / Bins unique_id lists (no M2M).
    waste_type_ids = models.JSONField(default=list, blank=True)

    trip_date = models.DateField()
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)

    driver_id = models.CharField(max_length=30, db_column="driver_id", db_index=True)
    operator_id = models.CharField(max_length=30, db_column="operator_id", db_index=True)
    extra_operator_ids = models.JSONField(default=list, blank=True)

    collected_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Auto-computed as the sum of all BinCollectionEvent weights for this trip.",
    )
    household_collected_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Auto-computed as the sum of all WasteCollection totals linked to this trip.",
    )

    vehicle_id = models.CharField(max_length=40, db_column="vehicle_id", db_index=True)
    bin_ids = models.JSONField(default=list, blank=True)

    remarks = models.TextField(null=True, blank=True)
    log_status = models.CharField(
        max_length=20,
        choices=LOG_STATUS_CHOICES,
        default=LOG_STATUS_DRAFT,
        db_index=True,
    )

    verified_by_id = models.CharField(max_length=50, db_column="verified_by", null=True, blank=True, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-trip_date", "-created_at"]
        indexes = [
            models.Index(fields=["trip_date", "log_status"]),
            models.Index(fields=["collection_point_id", "trip_date"]),
        ]

    def __str__(self):
        return self.unique_id

    # ---- plain-reference lookups (request-cached) --------------------
    @property
    def trip_assignment(self):
        return ref_cache.get(DailyTripAssignment, self.trip_assignment_id, "unique_id")

    @property
    def staff_template(self):
        return ref_cache.get(StaffTemplate, self.staff_template_id, "unique_id")

    @property
    def alt_staff_template(self):
        return ref_cache.get(AlternativeStaffTemplate, self.alt_staff_template_id, "unique_id")

    @property
    def collection_point(self):
        return ref_cache.get(Collection_point, self.collection_point_id, "unique_id")

    @property
    def driver(self):
        return ref_cache.get(Staffcreation, self.driver_id, "staff_unique_id")

    @property
    def operator(self):
        return ref_cache.get(Staffcreation, self.operator_id, "staff_unique_id")

    @property
    def vehicle(self):
        return ref_cache.get(VehicleCreation, self.vehicle_id, "unique_id")

    @property
    def verified_by(self):
        return ref_cache.get(Account, self.verified_by_id)

    @property
    def waste_types(self):
        return WasteType.objects.filter(unique_id__in=self.waste_type_ids or [])

    @property
    def extra_operators(self):
        return Staffcreation.objects.filter(staff_unique_id__in=self.extra_operator_ids or [])

    @property
    def bins(self):
        return Bins.objects.filter(unique_id__in=self.bin_ids or [])

    def _resolve_effective_staff_template(self):
        assignment = self.trip_assignment
        return assignment.effective_template if assignment else None

    def autofill_from_assignment(self):
        assignment = self.trip_assignment
        if not assignment:
            return

        copy_flat_geo(self, assignment)
        if not self.collection_point_id:
            first_child = (
                assignment.trip_collection_points
                .filter(is_deleted=False)
                .order_by("sequence")
                .first()
            )
            if first_child:
                self.collection_point_id = first_child.collection_point_id
        self.trip_date = assignment.trip_date
        self.actual_start_time = self.actual_start_time or assignment.actual_start_time
        self.actual_end_time = self.actual_end_time or assignment.actual_end_time

        # DailyTripAssignment references are plain unique_ids; this model's
        # own staff_template_id / alt_staff_template_id are still ForeignKeys.
        self.staff_template_id = assignment.staff_template_id
        self.alt_staff_template_id = assignment.alt_staff_template_id

        effective_template = self._resolve_effective_staff_template()
        if effective_template:
            # Template staff are plain staff_unique_ids; this model's own
            # driver_id / operator_id are still ForeignKeys.
            self.driver_id = effective_template.driver_id
            self.operator_id = effective_template.operator_id

        if assignment.vehicle_id:
            self.vehicle_id = assignment.vehicle_id
        elif assignment.trip_plan:
            self.vehicle_id = assignment.trip_plan.vehicle_id
        # Waste types follow the assignment (stored as a plain id list).
        self.waste_type_ids = list(assignment.waste_type_ids or [])

    def sync_from_household_collections(self):
        """Aggregate household waste weight from WasteCollection records for this trip.

        Mirrors sync_from_secondary_bin_collection_events() — only overrides when records exist
        so that manually-entered values are preserved when no WasteCollections are linked.
        """
        from app.models.core_modules.daily_operations.waste_collection import WasteCollection

        records = WasteCollection.objects.filter(
            trip_assignment_id=self.trip_assignment_id,
            is_deleted=False,
        )
        if not records.exists():
            return

        total = records.aggregate(total=Sum("total_quantity"))["total"]
        self.household_collected_weight_kg = Decimal(str(total or 0))
        DailyTripLog.objects.filter(pk=self.pk).update(
            household_collected_weight_kg=self.household_collected_weight_kg,
        )

    def sync_from_secondary_bin_collection_events(self):
        """Aggregate total collected weight from BinCollectionEvent records for this trip.

        Only overrides collected_weight_kg when bin-scan events actually exist.
        When no events are present the manually-entered value is preserved so that
        operators who enter weight directly (without bin scanning) are not silently
        zeroed out.
        """
        from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent

        events = BinCollectionEvent.objects.filter(
            trip_assignment_id=self.trip_assignment_id,
            is_deleted=False,
        )
        if not events.exists():
            # No bin-scan events — keep whatever was manually entered.
            return

        total = events.aggregate(total=Sum("collected_weight_kg"))["total"]
        self.collected_weight_kg = total or Decimal("0")
        DailyTripLog.objects.filter(pk=self.pk).update(
            collected_weight_kg=self.collected_weight_kg,
        )

    def clean(self):
        super().clean()

        if not self.trip_assignment_id:
            return

        assignment = self.trip_assignment
        if assignment.status == DailyTripAssignment.STATUS_CANCELLED:
            raise ValidationError("Cannot create a log for a cancelled trip.")

        if self.pk:
            previous = DailyTripLog.objects.filter(pk=self.pk).first()
            if previous and previous.log_status == self.LOG_STATUS_VERIFIED:
                raise ValidationError("Verified trip logs are read-only.")

        if self.log_status != self.LOG_STATUS_DRAFT:
            bin_weight = self.collected_weight_kg or Decimal("0")
            household_weight = self.household_collected_weight_kg or Decimal("0")
            if bin_weight <= 0 and household_weight <= 0:
                raise ValidationError(
                    "Either collected_weight_kg or household_collected_weight_kg must be "
                    "greater than 0 before submitting."
                )

        vehicle_capacity = getattr(self.vehicle, "capacity", None)
        trip_capacity = getattr(assignment.trip_plan, "max_vehicle_capacity_kg", None)
        capacity = vehicle_capacity or trip_capacity
        if capacity and self.collected_weight_kg:
            if Decimal(self.collected_weight_kg) > Decimal(capacity):
                raise ValidationError("collected_weight_kg cannot exceed vehicle capacity.")

    def save(self, *args, **kwargs):
        self.autofill_from_assignment()
        if not self.unique_id:
            self.unique_id = _generate_daily_trip_log_unique_id()

        self.full_clean()
        super().save(*args, **kwargs)


        self.sync_from_secondary_bin_collection_events()
        self.sync_from_household_collections()

        if self.log_status in {self.LOG_STATUS_SUBMITTED, self.LOG_STATUS_VERIFIED}:
            assignment = self.trip_assignment
            if assignment.status != DailyTripAssignment.STATUS_COMPLETED:
                # Route through the model so this path stamps `actual_end_at`
                # too — writing only the wall-clock `actual_end_time` here left
                # log-completed trips with a null authoritative timestamp, and
                # the app computes elapsed time from `actual_end_at`.
                # mark_ended() saves itself.
                assignment.mark_ended()
