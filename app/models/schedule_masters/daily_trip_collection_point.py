from django.db import models
from django.utils import timezone

from app.models.assets.bins import Bins
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


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

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="daily_trip_collection_points",
        db_column="company_id",
        null=True,
        blank=True,
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="daily_trip_collection_points",
        db_column="project_id",
        null=True,
        blank=True,
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
    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="daily_trip_collection_points",
        db_column="zone_id",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="daily_trip_collection_points",
        db_column="ward_id",
        null=True,
        blank=True,
    )
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="daily_trip_collection_points",
        db_column="panchayat_id",
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
        if self.trip_assignment_id_id and not self.company_id_id:
            assignment = self.trip_assignment_id
            self.company_id = assignment.company_id
            self.project_id = assignment.project_id
        if self.collection_point_id_id:
            collection_point = self.collection_point_id
            self.panchayat_id = collection_point.panchayat_id
            self.ward_id = collection_point.ward_id
            self.zone_id = (
                collection_point.ward_id.zone_id
                if collection_point.ward_id_id
                else None
            )
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
