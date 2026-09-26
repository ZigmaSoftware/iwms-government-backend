from datetime import timedelta

from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.masters.ward import Ward
from app.utils.hierarchy import copy_flat_geo
from app.utils import ref_cache


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

    # Only the assignment's OWN children — excludes carried_over_collection_points/
    # carried_over_household_collections (stops carried in FROM a different
    # assignment), retrip_source_requests and breakdown_source (point back at
    # whichever retrip/breakdown created THIS assignment as a continuation of
    # another one), and attendances (TripAttendance has no is_deleted field,
    # not soft-deletable). See app/utils/cascade_delete.py.
    CASCADE_SOFT_DELETE = (
        "trip_collection_points",
        "trip_household_collections",
        "secondary_bin_collection_events",
        "waste_collections",
        "daily_trip_log",
        "vehicle_breakdown",
        "retrip_requests",
        "unassignedstaffpool",
    )

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

    # Plain unique_id references (no DB relation); the `trip_plan` /
    # `staff_template` / `alt_staff_template` / `vehicle` properties resolve them.
    trip_plan_id = models.CharField(max_length=30, db_column="trip_plan_id")

    staff_template_id = models.CharField(max_length=20, db_column="staff_template_id", db_index=True)

    alt_staff_template_id = models.CharField(
        max_length=50, null=True, blank=True, db_column="alt_staff_template_id", db_index=True
    )

    # ------------------------------------------------------------------
    # LOCATION
    # ------------------------------------------------------------------

    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    # Inherited from the Trip Plan on create (see `save`), can be narrowed
    # per-trip the same way `waste_types` already is.
    # Ward / WasteType unique_id lists (no M2M); `wards` / `waste_types` /
    # `household_waste_types` properties return QuerySets.
    ward_ids = models.JSONField(default=list, blank=True)

    # ------------------------------------------------------------------
    # WASTE TYPE
    # ------------------------------------------------------------------

    # Waste types collected on this daily trip (inherited from the Trip Plan;
    # can be narrowed per-trip).
    waste_type_ids = models.JSONField(default=list, blank=True)

    # Multiple waste types for household collection stops on this trip
    household_waste_type_ids = models.JSONField(default=list, blank=True)

    # ------------------------------------------------------------------
    # VEHICLE (explicit for operator-mobile flow)
    # ------------------------------------------------------------------

    vehicle_id = models.CharField(
        max_length=40, null=True, blank=True, db_column="vehicle_id", db_index=True
    )

    # ------------------------------------------------------------------
    # SCHEDULING
    # ------------------------------------------------------------------

    trip_date = models.DateField()
    scheduled_time = models.TimeField()

    # Wall-clock times kept for backward compatibility — dashboards, the
    # DailyTripLog mirror and the mobile serializer all still read these. They
    # are DERIVED from the `_at` datetimes below; never stamp them directly,
    # use mark_started() / mark_ended().
    actual_start_time = models.TimeField(null=True, blank=True)
    actual_end_time = models.TimeField(null=True, blank=True)

    # The authoritative timestamps. TimeField alone cannot express a trip that
    # crosses midnight (end < start reads as a negative duration) and carries no
    # timezone, which already bit us: the scan path stamped IST via
    # `localtime()` while the admin status endpoint stamped UTC via `now()`, so
    # the same column held values 5h30m apart depending on the caller.
    actual_start_at = models.DateTimeField(null=True, blank=True, db_index=True)
    actual_end_at = models.DateTimeField(null=True, blank=True)

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
            models.Index(fields=["district_id", "trip_date"]),
        ]

    # ------------------------------------------------------------------
    # UNIQUE_ID GENERATION
    # ------------------------------------------------------------------

    # ---- plain-reference lookups (request-cached) --------------------
    @property
    def trip_plan(self):
        return ref_cache.get(TripPlan, self.trip_plan_id, "unique_id")

    @property
    def staff_template(self):
        return ref_cache.get(StaffTemplate, self.staff_template_id, "unique_id")

    @property
    def alt_staff_template(self):
        return ref_cache.get(AlternativeStaffTemplate, self.alt_staff_template_id, "unique_id")

    @property
    def effective_template(self):
        """The substitution template when one is active, else the base one."""
        return self.alt_staff_template or self.staff_template

    @property
    def vehicle(self):
        return ref_cache.get(VehicleCreation, self.vehicle_id, "unique_id")

    @property
    def trip_collection_points(self):
        """DailyTripCollectionPoint rows of this assignment (plain
        trip_assignment_id); replaces the reverse FK accessor."""
        from app.models.core_modules.daily_operations.daily_trip_collection_point import (
            DailyTripCollectionPoint,
        )

        return DailyTripCollectionPoint.objects.filter(trip_assignment_id=self.unique_id)

    @property
    def trip_household_collections(self):
        """DailyTripHouseholdCollection rows of this assignment (plain
        trip_assignment_id); replaces the reverse FK accessor."""
        from app.models.core_modules.daily_operations.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )

        return DailyTripHouseholdCollection.objects.filter(trip_assignment_id=self.unique_id)

    @property
    def secondary_bin_collection_events(self):
        """BinCollectionEvent rows of this assignment (plain trip_assignment_id)."""
        from app.models.core_modules.daily_operations.secondary_bin_collection_event import (
            BinCollectionEvent,
        )

        return BinCollectionEvent.objects.filter(trip_assignment_id=self.unique_id)

    @property
    def daily_trip_log(self):
        """This assignment's DailyTripLog (plain trip_assignment_id), or None;
        replaces the reverse one-to-one accessor."""
        from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog

        return DailyTripLog.objects.filter(trip_assignment_id=self.unique_id).first()

    @property
    def retrip_requests(self):
        """TripRetripRequest rows raised on this assignment (plain
        assignment_id); replaces the reverse FK accessor."""
        from app.models.core_modules.daily_operations.trip_retrip_request import (
            TripRetripRequest,
        )

        return TripRetripRequest.objects.filter(assignment_id=self.unique_id)

    @property
    def vehicle_breakdown(self):
        """This assignment's VehicleBreakdown (plain trip_assignment_id), or
        None; replaces the reverse one-to-one accessor."""
        from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown

        return VehicleBreakdown.objects.filter(trip_assignment_id=self.unique_id).first()

    @property
    def waste_collections(self):
        """WasteCollection rows linked to this assignment (plain
        trip_assignment_id); replaces the reverse FK accessor."""
        from app.models.core_modules.daily_operations.waste_collection import WasteCollection

        return WasteCollection.objects.filter(trip_assignment_id=self.unique_id)

    @property
    def wards(self):
        return Ward.objects.filter(unique_id__in=self.ward_ids or [])

    @property
    def waste_types(self):
        return WasteType.objects.filter(unique_id__in=self.waste_type_ids or [])

    @property
    def household_waste_types(self):
        return WasteType.objects.filter(unique_id__in=self.household_waste_type_ids or [])

    def save(self, *args, **kwargs):
        plan = self.trip_plan
        if plan:
            self.staff_template_id = self.staff_template_id or plan.staff_template_id
            self.vehicle_id = self.vehicle_id or plan.vehicle_id
            copy_flat_geo(self, plan, only_empty=True)
            self.scheduled_time = self.scheduled_time or plan.scheduled_time
            # Default wards / waste types from the plan before the insert, so
            # the post_save stop-copy signal already sees them.
            if not self.waste_type_ids:
                self.waste_type_ids = list(plan.waste_type_ids or [])
            if not self.ward_ids:
                self.ward_ids = list(plan.ward_ids or [])
        if not self.unique_id:
            self.unique_id = _generate_trip_assignment_unique_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id

    # ------------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------------
    # A stop is "resolved" for the day when it is Collected (done) or Missed
    # (attempted, nothing to collect). "Skipped" / collect-later is explicitly
    # NOT resolved — that is what a Re-Trip request carries over.
    #
    # The two stop models spell "missed" differently: a bin stop uses "Missed",
    # while a household stop's STATUS_MISSED is the label "Not Available". Never
    # share one status tuple between them — a household marked Not Available
    # would read as pending forever and the trip could never be ended. Always
    # resolve against each model's own constants, as
    # `operator_mobile.helpers.assignment_is_finished` does.
    RESOLVED_STOP_STATUSES = ("Collected", "Missed")

    def pending_bin_stops(self):
        """Bin collection points still awaiting the driver."""
        from app.models.core_modules.daily_operations.daily_trip_collection_point import (
            DailyTripCollectionPoint,
        )

        return self.trip_collection_points.filter(is_deleted=False).exclude(
            status__in=(
                DailyTripCollectionPoint.STATUS_COLLECTED,
                DailyTripCollectionPoint.STATUS_MISSED,
            )
        )

    def pending_household_stops(self):
        """Household stops still awaiting the driver."""
        from app.models.core_modules.daily_operations.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )

        return DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id=self, is_deleted=False
        ).exclude(
            status__in=(
                DailyTripHouseholdCollection.STATUS_COLLECTED,
                DailyTripHouseholdCollection.STATUS_MISSED,
            )
        )

    def has_pending_stops(self):
        return self.pending_bin_stops().exists() or self.pending_household_stops().exists()

    def mark_started(self, at=None):
        """Put the trip In Progress and stamp the start timestamps.

        Idempotent: calling it on an already-started trip is a no-op, so the
        explicit driver action and the implicit first-scan path can both call
        it without fighting over the timestamp. Also backfills a start time for
        a trip that was forced In Progress without one (the vehicle-breakdown
        approval path does exactly that).
        """
        if self.status in (self.STATUS_COMPLETED, self.STATUS_CANCELLED):
            return False

        started_at = at or timezone.now()
        update_fields = ["updated_at"]

        if self.status != self.STATUS_IN_PROGRESS:
            self.status = self.STATUS_IN_PROGRESS
            update_fields.append("status")

        if not self.actual_start_at:
            self.actual_start_at = started_at
            self.actual_start_time = timezone.localtime(started_at).time()
            update_fields += ["actual_start_at", "actual_start_time"]

        if len(update_fields) == 1:  # nothing but updated_at — already started
            return False

        self.save(update_fields=update_fields)
        return True

    def mark_ended(self, at=None):
        """Close the trip and stamp the end timestamps. Idempotent."""
        if self.status == self.STATUS_COMPLETED:
            return False

        ended_at = at or timezone.now()
        update_fields = ["status", "updated_at"]
        self.status = self.STATUS_COMPLETED

        if not self.actual_end_at:
            self.actual_end_at = ended_at
            self.actual_end_time = timezone.localtime(ended_at).time()
            update_fields += ["actual_end_at", "actual_end_time"]

        # A trip can be completed without ever having been explicitly started
        # (all work done through scans before this feature existed). Backfill so
        # duration math never sees a null start against a real end.
        if not self.actual_start_at:
            self.actual_start_at = ended_at
            self.actual_start_time = timezone.localtime(ended_at).time()
            update_fields += ["actual_start_at", "actual_start_time"]

        self.save(update_fields=update_fields)
        return True

    @property
    def total_trip_time(self):
        """Wall-clock duration from `actual_start_at` to `actual_end_at`, or to
        now while still In Progress. `None` until the trip has been started —
        never derived from the legacy `actual_start_time`/`actual_end_time`
        TimeFields, which carry no date and (historically) mixed timezones.
        """
        if not self.actual_start_at:
            return None
        end = self.actual_end_at or timezone.now()
        diff = end - self.actual_start_at
        return diff if diff.total_seconds() >= 0 else timedelta(0)

    def trip_count(self):
        """This assignment's 1-based position among all assignments made today
        for the same trip plan — the ordinary run is `1`; a Re-Trip
        continuation (`app/services/retrip_service.py`, same `trip_plan_id`
        and `trip_date`, a fresh row with no direct FK back to its source) is
        `2`, and so on for a chain of same-day re-trips. Ordered by
        `created_at` so the count reflects the order the shifts actually
        happened in, not unique_id string order.
        """
        siblings = list(
            DailyTripAssignment.objects.filter(
                trip_plan_id=self.trip_plan_id, trip_date=self.trip_date,
                is_deleted=False,
            ).order_by("created_at", "unique_id").values_list("unique_id", flat=True)
        )
        try:
            return siblings.index(self.unique_id) + 1
        except ValueError:
            # Not persisted yet (unsaved instance) — it would be the next one.
            return len(siblings) + 1

    def mark_completed_if_all_cps_collected(self, auto_end=True):
        """Returns True once every bin stop is resolved (Collected/Missed).

        [auto_end] controls whether "resolved" actually closes the trip
        (`mark_ended()`) or just reports the fact without touching status.
        Callers on the DRIVER APP's own write path (mark_collected/mark_status
        on DailyTripCollectionPoint) pass `auto_end=False`: closing a trip is
        now something the driver confirms — see `TripCompletionNudge` and
        `TripLifecycleControl` — not something that happens invisibly the
        moment the last stop is scanned. Admin/web CRUD
        (secondary_bin_collection_event_viewset.py,
        daily_trip_collection_point_viewset.py) and the backfill script keep
        the default `True`: an admin editing a record directly has no
        "confirm end trip" step to defer to.
        """
        children = self.trip_collection_points.filter(is_deleted=False)
        if not children.exists():
            return False
        # A missed stop is operationally resolved for the day but contributes
        # zero weight. "Skipped" / collect-later remains unresolved.
        if children.exclude(status__in=self.RESOLVED_STOP_STATUSES).exists():
            return False
        if self.status == self.STATUS_COMPLETED:
            return True
        if not auto_end:
            return True

        self.mark_ended()
        return True
