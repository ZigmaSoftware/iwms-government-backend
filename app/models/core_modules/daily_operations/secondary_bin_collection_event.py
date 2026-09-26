from django.db import models
from django.utils import timezone

from app.models.masters.waste_masters.bins import Bins
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.masters.ward import Ward
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo
from app.utils import ref_cache


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


    # Plain unique_id references (no DB relation); the properties below
    # (`trip_assignment`, `bin`, `vehicle`, ...) resolve them.
    trip_assignment_id = models.CharField(max_length=50, db_column="trip_assignment_id")
    trip_collection_point_id = models.CharField(max_length=30, db_column="trip_collection_point_id", db_index=True)

    collection_point_id = models.CharField(max_length=30, db_column="collection_point_id", db_index=True)
    bin_id = models.CharField(max_length=30, db_column="bin_id", db_index=True)
    location_node_id = models.CharField(max_length=30, db_column="location_node_id", null=True, blank=True, db_index=True)
    waste_type_id = models.CharField(max_length=100, db_column="waste_type_id", db_index=True)
    vehicle_id = models.CharField(max_length=40, db_column="vehicle_id", null=True, blank=True, db_index=True)
    # Approved breakdown that re-routed this collection to a replacement vehicle.
    vehicle_breakdown_id = models.CharField(max_length=50, db_column="vehicle_breakdown_id", null=True, blank=True, db_index=True)



    # Flat geo scope block — copied from the linked DailyTripAssignment on
    # save so bin-collection rows can be corporation-scoped directly rather
    # than only through the parent trip assignment (see B1). Plain
    # CharFields holding the related row's unique_id (no DB relation/join),
    # matching the rest of the geo-hierarchy convention.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, db_column="ward_id", null=True, blank=True, db_index=True)

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

    # ---- plain-reference lookups (request-cached) --------------------
    @property
    def trip_assignment(self):
        return ref_cache.get(DailyTripAssignment, self.trip_assignment_id, "unique_id")

    @property
    def trip_collection_point(self):
        return ref_cache.get(DailyTripCollectionPoint, self.trip_collection_point_id, "unique_id")

    @property
    def collection_point(self):
        return ref_cache.get(Collection_point, self.collection_point_id, "unique_id")

    @property
    def bin(self):
        return ref_cache.get(Bins, self.bin_id, "unique_id")

    @property
    def location_node(self):
        from app.models.masters.hierarchy_tree import HierarchyNode

        return ref_cache.get(HierarchyNode, self.location_node_id, "unique_id")

    @property
    def waste_type(self):
        return ref_cache.get(WasteType, self.waste_type_id, "unique_id")

    @property
    def vehicle(self):
        return ref_cache.get(VehicleCreation, self.vehicle_id, "unique_id")

    @property
    def vehicle_breakdown(self):
        from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown

        return ref_cache.get(VehicleBreakdown, self.vehicle_breakdown_id, "unique_id")

    @property
    def ward(self):
        return ref_cache.get(Ward, self.ward_id, "unique_id")

    def save(self, *args, **kwargs):
        # Inherit corporation / local-body scope from the parent trip
        # assignment on first write. `only_empty` preserves explicit values.
        assignment = self.trip_assignment
        if assignment and not self.corporation_id:
            copy_flat_geo(self, assignment, only_empty=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.unique_id
