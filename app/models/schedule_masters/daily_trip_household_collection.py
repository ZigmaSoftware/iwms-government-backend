from django.db import models
from django.utils import timezone

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.customer_masters.wastecollection import WasteCollection
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.superadmin.common_masters.state import State
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


def generate_dthc_id():
    return f"DTHC-{generate_unique_id(length=10)}"


class DailyTripHouseholdCollection(BaseMaster):
    """One row per household stop within a daily trip assignment.

    Created automatically (via signal) when a DailyTripAssignment is saved,
    mirroring every household_collection stop from the linked TripPlan.
    Marked collected when the corresponding WasteCollection record is saved.
    """

    STATUS_PENDING = "Pending"
    STATUS_COLLECTED = "Collected"
    STATUS_NOT_COLLECTED = "Not Collected"
    STATUS_COLLECT_LATER = "Collect Later"
    STATUS_SKIPPED = "Skipped"
    # "Not Available" is the canonical label for a household that couldn't be
    # collected (what the mobile app's "Not available" action produces). It was
    # previously stored/shown as "Missed"; renamed so app, backend and web match.
    STATUS_MISSED = "Not Available"

    COLLECTION_TYPE_HOUSEHOLD = "household_collection"
    COLLECTION_TYPE_BULK = "bulk_waste_collection"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COLLECTED, "Collected"),
        (STATUS_COLLECT_LATER, "Collect Later"),
        (STATUS_MISSED, "Not Available"),
        # Legacy values kept so historical rows still validate.
        (STATUS_NOT_COLLECTED, "Not Collected"),
        (STATUS_SKIPPED, "Skipped"),
    ]
    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
        (COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_dthc_id,
        editable=False,
    )


    trip_assignment_id = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.CASCADE,
        db_column="trip_assignment_id",
        to_field="unique_id",
        related_name="trip_household_collections",
    )

    customer_id = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        db_column="customer_id",
        to_field="unique_id",
        related_name="daily_trip_household_collections",
    )

    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_HOUSEHOLD,
        db_index=True,
    )

    # Filled when the WasteCollection record is saved for this customer + trip
    waste_collection_id = models.ForeignKey(
        WasteCollection,
        on_delete=models.SET_NULL,
        db_column="waste_collection_id",
        related_name="daily_trip_household_collections",
        null=True,
        blank=True,
    )

    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_household_collections",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_household_collections",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_household_collections",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_household_collections",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_household_collections",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_household_collections",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_household_collections",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_trip_household_collections",
        to_field="unique_id",
        db_column="panchayat_id",
    )

    sequence = models.PositiveIntegerField(default=1)

    is_collected = models.BooleanField(default=False, db_index=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    collected_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Copied from WasteCollection.total_quantity when marked collected.",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    status_reason = models.TextField(null=True, blank=True)

    # Captured when a driver/operator marks the stop Skipped/Missed from the app
    # (waste/mark-household-status/). No WasteCollection exists in that case, so
    # the reason and the device location are recorded here for audit.
    status_reason = models.TextField(null=True, blank=True)
    status_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    status_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
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
                fields=["trip_assignment_id", "customer_id", "collection_type"],
                name="uniq_household_per_trip_assignment",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.customer_id_id:
            copy_flat_geo(self, self.customer_id)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_assignment_id_id}:customer:{self.customer_id_id}:{self.collection_type}"

    def mark_collected(self, waste_collection, collected_at=None):
        from decimal import Decimal
        self.waste_collection_id = waste_collection
        self.collected_weight_kg = Decimal(str(waste_collection.total_quantity or 0))
        self.collected_at = collected_at or timezone.now()
        self.is_collected = True
        self.status = self.STATUS_COLLECTED
        self.save(update_fields=[
            "waste_collection_id",
            "collected_weight_kg",
            "collected_at",
            "is_collected",
            "status",
            "updated_at",
        ])
