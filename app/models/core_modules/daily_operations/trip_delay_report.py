"""Driver-reported delays that are NOT a breakdown.

A puncture, a minor repair, a blocked road, a queue at the plant: the vehicle
is still serviceable and the trip carries on, so none of the breakdown
machinery applies — no replacement vehicle, no alternative crew, no
continuation assignment. What the supervisor needs is simply to know the trip
is running late and why.

That is the whole design: an append-only log with an acknowledgement
workflow, deliberately kept out of `VehicleBreakdown` (one breakdown per trip,
replacement vehicle/crew, approval flow — none of which a puncture needs).

Plain id references (no DB relations): one trip can legitimately be delayed
several times in a day. The trip's flat geography is copied on save so the
rows are geo-scoped on their own columns, like VehicleBreakdown.
"""

from django.db import models, transaction
from django.utils import timezone

from app.utils import ref_cache
from app.utils.base_models import BaseMaster
from app.utils.hierarchy import copy_flat_geo


def _generate_trip_delay_id():
    """`DLY-YYYY-MM-NNN`, sequential within the month.

    Mirrors `_generate_vehicle_breakdown_id` — same select_for_update pattern
    so two drivers reporting at once cannot mint the same id.
    """
    today = timezone.localdate()
    prefix = f"DLY-{today.year}-{today.month:02d}"
    with transaction.atomic():
        existing = (
            TripDelayReport.objects.select_for_update()
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


class TripDelayReport(BaseMaster):

    STATUS_REPORTED = "REPORTED"
    STATUS_ACKNOWLEDGED = "ACKNOWLEDGED"
    STATUS_RESOLVED = "RESOLVED"

    STATUS_CHOICES = [
        (STATUS_REPORTED, "Reported"),
        (STATUS_ACKNOWLEDGED, "Acknowledged"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    DELAY_REASON_CHOICES = [
        ("PUNCTURE", "Puncture / Tyre"),
        ("MINOR_REPAIR", "Minor Repair"),
        ("TRAFFIC", "Traffic"),
        ("ROAD_BLOCKED", "Road Blocked"),
        ("FUEL", "Refuelling"),
        ("WEATHER", "Weather"),
        ("PUBLIC_OBSTRUCTION", "Public Obstruction"),
        ("WAITING_AT_PLANT", "Waiting at Plant"),
        ("OTHER", "Other"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=_generate_trip_delay_id,
        editable=False,
    )

    # DailyTripAssignment.unique_id — NOT unique: a trip can be delayed more
    # than once.
    trip_assignment_id = models.CharField(max_length=50, db_index=True)

    # Staffcreation.staff_unique_id of the reporting driver/operator.
    reported_by_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)

    delay_reason = models.CharField(
        max_length=30,
        choices=DELAY_REASON_CHOICES,
    )
    # The point of the whole feature — enforced non-blank at the serializer,
    # where a friendly message can be returned.
    delay_remarks = models.TextField()

    # Optional, but what lets a supervisor tell "10 minutes" from "two hours"
    # without reading every remark.
    estimated_delay_minutes = models.PositiveIntegerField(null=True, blank=True)

    delay_time = models.TimeField(null=True, blank=True)
    delay_lat = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    delay_lng = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    delay_location = models.CharField(max_length=255, null=True, blank=True)
    evidence_image = models.ImageField(
        upload_to="trip_delay_evidence/%Y/%m/%d/", null=True, blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_REPORTED,
        db_index=True,
    )

    # Staffcreation.staff_unique_id of the acknowledging supervisor.
    acknowledged_by_id = models.CharField(max_length=30, null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    supervisor_remarks = models.TextField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # ── Flat geo scope block (copied from the trip assignment on save) ───
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.unique_id} ({self.get_delay_reason_display()})"

    def save(self, *args, **kwargs):
        # Stamp the wall-clock time of the delay on first write so the
        # supervisor list can show "reported at 09:41" without deriving it
        # from created_at in every serializer.
        if not self.delay_time:
            self.delay_time = timezone.localtime().time()
        # Inherit the trip's geography — a delay is never in a different local
        # body than the assignment it belongs to, and a null here would hide
        # the row from every geo-scoped list.
        if self.trip_assignment_id and not self.district_id:
            assignment = self.trip_assignment
            if assignment is not None:
                copy_flat_geo(self, assignment, only_empty=True)
        super().save(*args, **kwargs)

    def mark_acknowledged(self, *, by=None, remarks=None):
        """Supervisor has seen it. Idempotent."""
        if self.status != self.STATUS_REPORTED:
            return False
        self.status = self.STATUS_ACKNOWLEDGED
        self.acknowledged_by_id = getattr(by, "staff_unique_id", None) if by else None
        self.acknowledged_at = timezone.now()
        if remarks:
            self.supervisor_remarks = remarks
        self.save(update_fields=[
            "status", "acknowledged_by_id", "acknowledged_at",
            "supervisor_remarks", "updated_at",
        ])
        return True

    def mark_resolved(self, *, remarks=None):
        """Back on route. Idempotent."""
        if self.status == self.STATUS_RESOLVED:
            return False
        self.status = self.STATUS_RESOLVED
        self.resolved_at = timezone.now()
        if remarks:
            self.supervisor_remarks = remarks
        self.save(update_fields=[
            "status", "resolved_at", "supervisor_remarks", "updated_at",
        ])
        return True

    @property
    def trip_assignment(self):
        from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment

        return ref_cache.get(DailyTripAssignment, self.trip_assignment_id, "unique_id")

    @property
    def reported_by(self):
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        return ref_cache.get(Staffcreation, self.reported_by_id)

    @property
    def acknowledged_by(self):
        from app.models.superadmin.staff_management.staffcreation import Staffcreation

        return ref_cache.get(Staffcreation, self.acknowledged_by_id)
