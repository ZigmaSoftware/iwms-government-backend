from django.db import models
from django.utils import timezone

from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_hierarchy


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


    trip_assignment_id = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.CASCADE,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="trip_collection_points",
    )

    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        db_column="collection_point_id",
        to_field="unique_id",
        related_name="daily_trip_cps",
    )
    location_node = models.ForeignKey(
        "app.HierarchyNode",
        on_delete=models.SET_NULL,
        related_name="daily_trip_collection_points",
        to_field="unique_id",
        db_column="location_node_id",
        null=True,
        blank=True,
    )

    bin_id = models.ForeignKey(
        Bins,
        on_delete=models.PROTECT,
        db_column="bin_id",
        to_field="unique_id",
        related_name="daily_trip_cps",
    )

    sequence = models.PositiveIntegerField(default=1)
    
    is_collected = models.BooleanField(default=False, db_index=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_by = models.ForeignKey(
        Staffcreation,
        on_delete=models.SET_NULL,
        db_column="collected_by",
        to_field="staff_unique_id",
        related_name="collected_trip_cps",
        null=True,
        blank=True,
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
                fields=["trip_assignment_id", "collection_point_id"],
                name="uniq_trip_cp_per_assignment",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.collection_point_id_id:
            copy_hierarchy(self, self.collection_point_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_assignment_id_id}:{self.collection_point_id_id}"

    def mark_collected(self, weight_kg, collected_by, collected_at=None):
        self.collected_weight_kg = weight_kg
        self.collected_by = collected_by
        self.collected_at = collected_at or timezone.now()
        self.is_collected = True
        self.status = self.STATUS_COLLECTED
        self.save(update_fields=[
            "collected_weight_kg",
            "collected_by",
            "collected_at",
            "is_collected",
            "status",
            "updated_at",
        ])
        self.trip_assignment_id.mark_completed_if_all_cps_collected()
