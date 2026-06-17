from django.db import models
from django.utils import timezone

from app.models.customers.customercreation import CustomerCreation
from app.models.customers.wastecollection import WasteCollection
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.masters.zone import Zone
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


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
    STATUS_SKIPPED = "Skipped"
    STATUS_MISSED = "Missed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COLLECTED, "Collected"),
        (STATUS_SKIPPED, "Skipped"),
        (STATUS_MISSED, "Missed"),
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

    # Filled when the WasteCollection record is saved for this customer + trip
    waste_collection_id = models.ForeignKey(
        WasteCollection,
        on_delete=models.SET_NULL,
        db_column="waste_collection_id",
        related_name="daily_trip_household_collections",
        null=True,
        blank=True,
    )

    zone_id = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="daily_trip_household_collections",
        db_column="zone_id",
        null=True,
        blank=True,
    )
    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="daily_trip_household_collections",
        db_column="ward_id",
        null=True,
        blank=True,
    )
    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="daily_trip_household_collections",
        db_column="panchayat_id",
        null=True,
        blank=True,
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
                fields=["trip_assignment_id", "customer_id"],
                name="uniq_household_per_trip_assignment",
            ),
        ]

    def save(self, *args, **kwargs):
        # Denormalise location from customer
        if self.customer_id_id and not self.panchayat_id_id:
            customer = self.customer_id
            self.panchayat_id = getattr(customer, "panchayat_id", None)
            self.ward_id = getattr(customer, "ward_id", None)
            self.zone_id = getattr(customer, "zone_id", None)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_assignment_id_id}:customer:{self.customer_id_id}"

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
