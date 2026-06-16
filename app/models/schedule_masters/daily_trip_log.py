from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.masters.panchayat import Panchayat
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.staff_template import StaffTemplate
from app.models.schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.utils.base_models import Account, BaseMaster


def _generate_daily_trip_log_unique_id(company_id, project_id):
    today = timezone.localdate()
    prefix = f"DTL-{today.year}-{today.month:02d}"
    count = DailyTripLog.objects.filter(
        company_id=company_id,
        project_id=project_id,
        unique_id__startswith=f"{prefix}-",
    ).count()
    return f"{prefix}-{count + 1:03d}"


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

    trip_assignment_id = models.OneToOneField(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="daily_trip_log",
    )

    staff_template_id = models.ForeignKey(
        StaffTemplate,
        on_delete=models.PROTECT,
        db_column="staff_template_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
        null=True,
        blank=True,
    )
    alt_staff_template_id = models.ForeignKey(
        AlternativeStaffTemplate,
        on_delete=models.PROTECT,
        db_column="alt_staff_template_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
        null=True,
        blank=True,
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        db_column="company_id",
        related_name="daily_trip_logs",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        db_column="project_id",
        related_name="daily_trip_logs",
    )
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        db_column="panchayat_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
    )
    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        db_column="collection_point_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
        null=True,
        blank=True,
    )
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        db_column="waste_type_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
    )

    trip_date = models.DateField()
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)

    driver_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="driver_id",
        to_field="staff_unique_id",
        related_name="daily_trip_logs_as_driver",
    )
    operator_id = models.ForeignKey(
        Staffcreation,
        on_delete=models.PROTECT,
        db_column="operator_id",
        to_field="staff_unique_id",
        related_name="daily_trip_logs_as_operator",
    )
    extra_operator_ids = models.ManyToManyField(
        Staffcreation,
        blank=True,
        related_name="daily_trip_logs_as_extra_operator",
    )

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

    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="daily_trip_logs",
    )
    bin_ids = models.ManyToManyField(
        Bins,
        blank=True,
        related_name="daily_trip_logs",
    )

    remarks = models.TextField(null=True, blank=True)
    log_status = models.CharField(
        max_length=20,
        choices=LOG_STATUS_CHOICES,
        default=LOG_STATUS_DRAFT,
        db_index=True,
    )

    verified_by = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="verified_by",
        related_name="verified_daily_trip_logs",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-trip_date", "-created_at"]
        indexes = [
            models.Index(fields=["trip_date", "log_status"]),
            models.Index(fields=["company_id", "project_id", "trip_date"]),
            models.Index(fields=["collection_point_id", "trip_date"]),
        ]

    def __str__(self):
        return self.unique_id

    def _resolve_effective_staff_template(self):
        assignment = self.trip_assignment_id
        return assignment.alt_staff_template_id or assignment.staff_template_id

    def autofill_from_assignment(self):
        assignment = self.trip_assignment_id
        if not assignment:
            return

        self.company_id = assignment.company_id
        self.project_id = assignment.project_id
        self.panchayat_id = assignment.panchayat_id
        if not self.collection_point_id:
            first_child = (
                assignment.trip_collection_points
                .filter(is_deleted=False)
                .order_by("sequence")
                .first()
            )
            if first_child:
                self.collection_point_id = first_child.collection_point_id
        self.waste_type_id = assignment.waste_type_id
        self.trip_date = assignment.trip_date
        self.actual_start_time = self.actual_start_time or assignment.actual_start_time
        self.actual_end_time = self.actual_end_time or assignment.actual_end_time

        self.staff_template_id = assignment.staff_template_id
        self.alt_staff_template_id = assignment.alt_staff_template_id

        effective_template = self._resolve_effective_staff_template()
        if effective_template:
            self.driver_id = effective_template.driver_id
            self.operator_id = effective_template.operator_id

        if getattr(assignment, "vehicle_id", None):
            self.vehicle_id = assignment.vehicle_id
        elif getattr(assignment, "trip_plan_id", None):
            self.vehicle_id = assignment.trip_plan_id.vehicle_id

    def sync_from_household_collections(self):
        """Aggregate household waste weight from WasteCollection records for this trip.

        Mirrors sync_from_bin_collection_events() — only overrides when records exist
        so that manually-entered values are preserved when no WasteCollections are linked.
        """
        from app.models.customers.wastecollection import WasteCollection

        records = WasteCollection.objects.filter(
            trip_assignment_id=self.trip_assignment_id_id,
            is_deleted=False,
        )
        if not records.exists():
            return

        total = records.aggregate(total=Sum("total_quantity"))["total"]
        self.household_collected_weight_kg = Decimal(str(total or 0))
        DailyTripLog.objects.filter(pk=self.pk).update(
            household_collected_weight_kg=self.household_collected_weight_kg,
        )

    def sync_from_bin_collection_events(self):
        """Aggregate total collected weight from BinCollectionEvent records for this trip.

        Only overrides collected_weight_kg when bin-scan events actually exist.
        When no events are present the manually-entered value is preserved so that
        operators who enter weight directly (without bin scanning) are not silently
        zeroed out.
        """
        from app.models.schedule_masters.bin_collection_event import BinCollectionEvent

        events = BinCollectionEvent.objects.filter(
            trip_assignment_id=self.trip_assignment_id_id,
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

        assignment = self.trip_assignment_id
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

        vehicle_capacity = getattr(self.vehicle_id, "capacity", None)
        trip_capacity = getattr(assignment.trip_plan_id, "max_vehicle_capacity_kg", None)
        capacity = vehicle_capacity or trip_capacity
        if capacity and self.collected_weight_kg:
            if Decimal(self.collected_weight_kg) > Decimal(capacity):
                raise ValidationError("collected_weight_kg cannot exceed vehicle capacity.")

    def save(self, *args, **kwargs):
        self.autofill_from_assignment()
        if not self.unique_id:
            self.unique_id = _generate_daily_trip_log_unique_id(
                self.company_id, self.project_id
            )

        self.full_clean()
        super().save(*args, **kwargs)

        self.sync_from_bin_collection_events()
        self.sync_from_household_collections()

        if self.log_status in {self.LOG_STATUS_SUBMITTED, self.LOG_STATUS_VERIFIED}:
            assignment = self.trip_assignment_id
            if assignment.status != DailyTripAssignment.STATUS_COMPLETED:
                now_time = timezone.localtime().time()
                update_fields = ["status", "updated_at"]
                assignment.status = DailyTripAssignment.STATUS_COMPLETED
                if not assignment.actual_end_time:
                    assignment.actual_end_time = self.actual_end_time or now_time
                    update_fields.append("actual_end_time")
                assignment.save(update_fields=update_fields)
