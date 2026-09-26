from django.core.exceptions import ValidationError
from django.db import models

from app.models.masters.waste_masters.bins import Bins
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo
from app.utils import ref_cache


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

    # Plain unique_id references (no DB relation); the `trip_plan` /
    # `collection_point` / `bin` / `customer` properties resolve them.
    trip_plan_id = models.CharField(max_length=30, db_column="trip_plan_id")

    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_BIN,
        db_index=True,
    )

    # --- Bin Collection fields (required when collection_type == bin_collection) ---
    collection_point_id = models.CharField(
        max_length=30, null=True, blank=True, db_column="collection_point_id", db_index=True
    )
    bin_id = models.CharField(max_length=30, null=True, blank=True, db_column="bin_id", db_index=True)

    # --- Household Collection fields (required when collection_type == household_collection) ---
    customer_id = models.CharField(
        max_length=30, null=True, blank=True, db_column="customer_id", db_index=True
    )

    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
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

    def _lookup(self, model, value):
        return ref_cache.get(model, value, "unique_id")

    @property
    def trip_plan(self):
        return self._lookup(TripPlan, self.trip_plan_id)

    @property
    def collection_point(self):
        return self._lookup(Collection_point, self.collection_point_id)

    @property
    def bin(self):
        return self._lookup(Bins, self.bin_id)

    @property
    def customer(self):
        return self._lookup(CustomerCreation, self.customer_id)

    def clean(self):
        # A stop's type must match its plan's declared collection_type - a
        # plan generates exactly one category of daily work (see
        # TripPlan.collection_type), so a household_collection plan can only
        # carry household-type stops, and a bin_collection plan only bin
        # stops. (Whether a bulk stop may be added manually is enforced at
        # the API/serializer layer; the auto-generated bulk placeholder row
        # is still valid here.)
        if self.trip_plan and self.collection_type != self.trip_plan.collection_type:
            raise ValidationError(
                {"collection_type": "Stop type must match the trip plan's collection type."}
            )
        if self.collection_type == self.COLLECTION_TYPE_BIN:
            if not self.collection_point_id:
                raise ValidationError({"collection_point_id": "Collection point is required for bin collection."})
            if not self.bin_id:
                raise ValidationError({"bin_id": "Bin is required for bin collection."})
        elif self.collection_type in {self.COLLECTION_TYPE_HOUSEHOLD, self.COLLECTION_TYPE_BULK}:
            if not self.customer_id and not self.district_id and not self.trip_plan_id:
                raise ValidationError(
                    {"customer_id": "Select a customer or assign collection to a geographic area."}
                )

    def save(self, *args, **kwargs):
        source = self.collection_point or self.customer or self.trip_plan
        if source:
            copy_flat_geo(self, source)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.collection_type in {self.COLLECTION_TYPE_HOUSEHOLD, self.COLLECTION_TYPE_BULK} and self.customer_id:
            return f"{self.trip_plan_id} -> customer:{self.customer_id} (seq {self.sequence})"
        return f"{self.trip_plan_id} -> {self.collection_point_id} (seq {self.sequence})"
