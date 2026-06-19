from django.core.exceptions import ValidationError
from django.db import models

from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_tpcp_id():
    return f"TPCP-{generate_unique_id()}"


class TripPlanCollectionPoint(BaseMaster):
    """Master stop list for a TripPlan."""

    COLLECTION_TYPE_BIN = "bin_collection"
    COLLECTION_TYPE_HOUSEHOLD = "household_collection"

    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_BIN, "Bin Collection"),
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_tpcp_id,
        editable=False,
    )

    trip_plan_id = models.ForeignKey(
        TripPlan,
        on_delete=models.CASCADE,
        to_field="unique_id",
        related_name="plan_collection_points",
        db_column="trip_plan_id",
    )

    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_BIN,
        db_index=True,
    )

    # --- Bin Collection fields (required when collection_type == bin_collection) ---
    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plan_cps",
        db_column="collection_point_id",
        null=True,
        blank=True,
    )
    bin_id = models.ForeignKey(
        Bins,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plan_cps",
        db_column="bin_id",
        null=True,
        blank=True,
    )

    # --- Household Collection fields (required when collection_type == household_collection) ---
    customer_id = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="trip_plan_cps",
        db_column="customer_id",
        null=True,
        blank=True,
    )

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="trip_plan_collection_points",
        db_column="zone_id",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="trip_plan_collection_points",
        db_column="ward_id",
        null=True,
        blank=True,
    )
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="trip_plan_collection_points",
        db_column="panchayat_id",
        null=True,
        blank=True,
    )
    sequence = models.PositiveIntegerField(
        help_text="Visit order within the route.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive stops are skipped during auto-assignment.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip_plan_id", "sequence"]
        indexes = [
            models.Index(fields=["trip_plan_id", "is_active"]),
            models.Index(fields=["trip_plan_id", "collection_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_plan_id", "sequence"],
                name="uniq_sequence_per_trip_plan",
            ),
        ]

    def clean(self):
        if self.collection_type == self.COLLECTION_TYPE_BIN:
            if not self.collection_point_id_id:
                raise ValidationError({"collection_point_id": "Collection point is required for bin collection."})
            if not self.bin_id_id:
                raise ValidationError({"bin_id": "Bin is required for bin collection."})
        elif self.collection_type == self.COLLECTION_TYPE_HOUSEHOLD:
            if not self.customer_id_id:
                raise ValidationError({"customer_id": "Customer is required for household collection."})

    def save(self, *args, **kwargs):
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
        if self.collection_type == self.COLLECTION_TYPE_HOUSEHOLD and self.customer_id_id:
            return f"{self.trip_plan_id_id} -> customer:{self.customer_id_id} (seq {self.sequence})"
        return (
            f"{self.trip_plan_id_id} -> "
            f"{self.collection_point_id_id} (seq {self.sequence})"
        )
