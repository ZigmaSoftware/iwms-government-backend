from django.db import models
from django.utils import timezone

from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo
from app.utils import ref_cache
from app.utils.plain_ref import ref_id


def generate_daily_trip_cp_id():
    return f"DTCP-{generate_unique_id(length=10)}"


class DailyTripCollectionPoint(BaseMaster):
    STATUS_PENDING = "Pending"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COLLECTED = "Collected"
    STATUS_SKIPPED = "Skipped"
    STATUS_MISSED = "Missed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COLLECTED, "Collected"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_MISSED, "Missed"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_daily_trip_cp_id,
        editable=False,
    )


    # Plain unique_id references (no DB relation); `trip_assignment` /
    # `collection_point` / `bin` / `collected_by` / `carried_to_assignment`
    # properties resolve them.
    trip_assignment_id = models.CharField(max_length=50, db_column="trip_assignment_id")

    collection_point_id = models.CharField(max_length=30, db_column="collection_point_id", db_index=True)
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    bin_id = models.CharField(max_length=30, db_column="bin_id", db_index=True)

    sequence = models.PositiveIntegerField(default=1)
    
    is_collected = models.BooleanField(default=False, db_index=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_by_id = models.CharField(
        max_length=30, null=True, blank=True, db_column="collected_by", db_index=True
    )
    collected_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    status_reason = models.TextField(null=True, blank=True)
    status_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    status_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # Set by retrip_service.approve_retrip() on the SOURCE stop when it is
    # carried over to a continuation trip. Deliberately does not affect
    # `status` (still Pending/etc.) — see the comment in approve_retrip for
    # why the completion-percentage math depends on that.
    carried_to_assignment_id = models.CharField(
        max_length=50, null=True, blank=True, db_column="carried_to_assignment_id", db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip_assignment_id", "sequence"]
        indexes = [
            models.Index(fields=["trip_assignment_id", "is_collected"]),
            models.Index(fields=["trip_assignment_id", "sequence"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_assignment_id", "collection_point_id", "bin_id"],
                name="uniq_trip_cp_bin_per_assignment",
            ),
        ]

    @property
    def trip_assignment(self):
        return ref_cache.get(DailyTripAssignment, self.trip_assignment_id, "unique_id")

    @property
    def collection_point(self):
        return ref_cache.get(Collection_point, self.collection_point_id, "unique_id")

    @property
    def bin(self):
        return ref_cache.get(Bins, self.bin_id, "unique_id")

    @property
    def collected_by(self):
        return ref_cache.get(Staffcreation, self.collected_by_id, "staff_unique_id")

    @property
    def carried_to_assignment(self):
        return ref_cache.get(DailyTripAssignment, self.carried_to_assignment_id, "unique_id")

    def save(self, *args, **kwargs):
        cp = self.collection_point
        if cp:
            copy_flat_geo(self, cp)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_assignment_id}:{self.collection_point_id}"

    def mark_collected(self, weight_kg, collected_by, collected_at=None):
        self.collected_weight_kg = weight_kg
        self.collected_by_id = ref_id(collected_by)
        self.collected_at = collected_at or timezone.now()
        self.is_collected = True
        self.status = self.STATUS_COLLECTED
        self.status_reason = None
        self.status_latitude = None
        self.status_longitude = None
        self.save(update_fields=[
            "collected_weight_kg",
            "collected_by_id",
            "collected_at",
            "is_collected",
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "updated_at",
        ])
        # Closing the trip is now the driver's own confirmed action (see
        # TripCompletionNudge / TripLifecycleControl on the app side) rather
        # than something that happens invisibly the instant the last stop is
        # scanned — this call only updates whether every stop is resolved,
        # it no longer ends the trip itself.
        self.trip_assignment.mark_completed_if_all_cps_collected(auto_end=False)

    def mark_status(self, status, reason, latitude=None, longitude=None):
        self.status = status
        self.status_reason = reason
        self.status_latitude = latitude
        self.status_longitude = longitude
        self.is_collected = False
        self.collected_at = None
        self.collected_by_id = None
        if status in {self.STATUS_SKIPPED, self.STATUS_MISSED}:
            self.collected_weight_kg = None
        self.save(update_fields=[
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "is_collected",
            "collected_at",
            "collected_by_id",
            "collected_weight_kg",
            "updated_at",
        ])
        self.trip_assignment.mark_completed_if_all_cps_collected(auto_end=False)
