from django.db import models
from django.utils import timezone

from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo


def generate_secondary_bin_collection_event_id():
    return f"BCE-{generate_unique_id(length=10)}"


class BinCollectionEvent(BaseMaster):
    """One row per operator scan-and-submit. Permanent audit ledger."""

    STATUS_COLLECTED = "Collected"
    STATUS_NOT_COLLECTED = "Not Collected"
    STATUS_COLLECT_LATER = "Collect Later"

    STATUS_CHOICES = [
        (STATUS_COLLECTED, "Collected"),
        (STATUS_NOT_COLLECTED, "Not Collected"),
        (STATUS_COLLECT_LATER, "Collect Later"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_secondary_bin_collection_event_id,
        editable=False,
    )


    trip_assignment_id = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="secondary_bin_collection_events",
    )
    trip_collection_point_id = models.ForeignKey(
        DailyTripCollectionPoint,
        on_delete=models.PROTECT,
        db_column="trip_collection_point_id",
        to_field="unique_id",
        related_name="secondary_bin_collection_event",
    )

    collection_point_id = models.ForeignKey(
        Collection_point,
        on_delete=models.PROTECT,
        db_column="collection_point_id",
        to_field="unique_id",
        related_name="secondary_bin_collection_events",
    )
    bin_id = models.ForeignKey(
        Bins,
        on_delete=models.PROTECT,
        db_column="bin_id",
        to_field="unique_id",
        related_name="secondary_bin_collection_events",
    )
    location_node = models.ForeignKey(
        "app.HierarchyNode",
        on_delete=models.PROTECT,
        db_column="location_node_id",
        to_field="unique_id",
        related_name="secondary_bin_collection_events",
        null=True,
        blank=True,
    )
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.PROTECT,
        db_column="waste_type_id",
        to_field="unique_id",
        related_name="secondary_bin_collection_events",
    )
    vehicle_id = models.ForeignKey(
        VehicleCreation,
        on_delete=models.PROTECT,
        db_column="vehicle_id",
        to_field="unique_id",
        related_name="secondary_bin_collection_events",
        null=True,
        blank=True,
    )
    vehicle_breakdown_id = models.ForeignKey(
        "app.VehicleBreakdown",
        on_delete=models.SET_NULL,
        db_column="vehicle_breakdown_id",
        to_field="unique_id",
        related_name="secondary_bin_collection_events",
        null=True,
        blank=True,
        help_text="Approved breakdown that re-routed this collection to a replacement vehicle.",
    )



    # Flat geo scope block — copied from the linked DailyTripAssignment on
    # save so bin-collection rows can be corporation-scoped directly rather
    # than only through the parent trip assignment (see B1).
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_bin_collection_events",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_bin_collection_events",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_bin_collection_events",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_bin_collection_events",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_bin_collection_events",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_bin_collection_events",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_bin_collection_events",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="secondary_bin_collection_events",
        to_field="unique_id",
        db_column="panchayat_id",
    )
    ward = models.ForeignKey(
        Ward, on_delete=models.PROTECT, related_name="bin_collection_events",
        to_field="unique_id", db_column="ward_id", null=True, blank=True,
    )

    collected_weight_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_COLLECTED,
        db_index=True,
    )
    status_reason = models.TextField(null=True, blank=True)
    collection_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
        help_text="Date on which this bin collection was performed.",
    )
    
    driver_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    driver_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-collection_date", "-created_at"]
        indexes = [
            models.Index(fields=["trip_assignment_id", "created_at"]),
            models.Index(fields=["collection_date"]),
            # models.Index(fields=["operator_id", "created_at"]),
            # models.Index(fields=["panchayat_id", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        # Inherit corporation / local-body scope from the parent trip
        # assignment on first write. `only_empty` preserves explicit values.
        if self.trip_assignment_id_id and not self.corporation_id:
            copy_flat_geo(self, self.trip_assignment_id, only_empty=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id
