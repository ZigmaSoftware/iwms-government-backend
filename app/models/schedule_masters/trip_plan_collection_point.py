from django.core.exceptions import ValidationError
from django.db import models

from app.models.assets.bins import Bins
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.collection_point import Collection_point
from app.models.schedule_masters.trip_plan import TripPlan
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo


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

    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plan_collection_points",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plan_collection_points",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plan_collection_points",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plan_collection_points",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plan_collection_points",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plan_collection_points",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plan_collection_points",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trip_plan_collection_points",
        to_field="unique_id",
        db_column="panchayat_id",
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
            if not self.customer_id_id and not self.district_id and not self.trip_plan_id_id:
                raise ValidationError(
                    {"customer_id": "Select a customer or assign collection to a geographic area."}
                )

    def save(self, *args, **kwargs):
        if self.collection_point_id_id:
            copy_flat_geo(self, self.collection_point_id)
        elif self.customer_id_id:
            copy_flat_geo(self, self.customer_id)
        elif self.trip_plan_id_id:
            copy_flat_geo(self, self.trip_plan_id)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.collection_type in {self.COLLECTION_TYPE_HOUSEHOLD, self.COLLECTION_TYPE_BULK} and self.customer_id_id:
            return f"{self.trip_plan_id_id} -> customer:{self.customer_id_id} (seq {self.sequence})"
        return (
            f"{self.trip_plan_id_id} -> "
            f"{self.collection_point_id_id} (seq {self.sequence})"
        )
