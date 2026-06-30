from django.core.exceptions import ValidationError
from django.db import models

from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_hierarchy


def generate_tpcp_id():
    return f"TPCP-{generate_unique_id()}"


class TripPlanCollectionPoint(BaseMaster):
    """Master stop list for a TripPlan."""

    COLLECTION_TYPE_BIN = "bin_collection"
    COLLECTION_TYPE_HOUSEHOLD = "household_collection"
    COLLECTION_TYPE_BULK = "bulk_waste_collection"

    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_BIN, "Bin Collection"),
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
        (COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
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

    location_node = models.ForeignKey(
        "app.HierarchyNode",
        on_delete=models.SET_NULL,
        related_name="trip_plan_collection_points",
        to_field="unique_id",
        db_column="location_node_id",
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
        if self.trip_plan_id_id and self.collection_type != self.trip_plan_id.collection_type:
            raise ValidationError(
                {"collection_type": "Trip point collection type must match the Trip Plan collection type."}
            )

        if self.collection_type == self.COLLECTION_TYPE_BIN:
            if not self.collection_point_id_id:
                raise ValidationError({"collection_point_id": "Collection point is required for bin collection."})
            if not self.bin_id_id:
                raise ValidationError({"bin_id": "Bin is required for bin collection."})
        elif self.collection_type in {self.COLLECTION_TYPE_HOUSEHOLD, self.COLLECTION_TYPE_BULK}:
            if not self.customer_id_id and not self.location_node_id and not self.trip_plan_id_id:
                raise ValidationError(
                    {"customer_id": "Select a customer or assign collection to a hierarchy node."}
                )

    def save(self, *args, **kwargs):
        if self.collection_point_id_id:
            copy_hierarchy(self, self.collection_point_id)
        elif self.customer_id_id:
            copy_hierarchy(self, self.customer_id)
        elif self.trip_plan_id_id:
            copy_hierarchy(self, self.trip_plan_id)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.collection_type in {self.COLLECTION_TYPE_HOUSEHOLD, self.COLLECTION_TYPE_BULK} and self.customer_id_id:
            return f"{self.trip_plan_id_id} -> customer:{self.customer_id_id} (seq {self.sequence})"
        return (
            f"{self.trip_plan_id_id} -> "
            f"{self.collection_point_id_id} (seq {self.sequence})"
        )
