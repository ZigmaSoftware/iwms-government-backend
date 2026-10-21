from django.db import models
from django.utils import timezone

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo
from app.utils import ref_cache


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


    trip_assignment_id = models.CharField(max_length=50)

    customer_id = models.CharField(max_length=30, db_index=True)

    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_HOUSEHOLD,
        db_index=True,
    )

    # Filled when the WasteCollection record is saved for this customer + trip
    # — WasteCollection.unique_id as a plain string (no DB relation).
    waste_collection_id = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        db_index=True,
    )

    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)

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
    # Geotagged photo the driver must take when marking the stop Not
    # Available (waste/mark-household-status/).
    status_evidence_image = models.ImageField(
        upload_to="household_status_evidence/%Y/%m/%d/", null=True, blank=True
    )

    # Set when the customer taps "I'm home now" in the citizen app after the
    # driver marked this stop Collect Later (app/services/customer_availability.py).
    # The driver/crew are pushed, and if the stop still ends Not Available a
    # Missed Pickup complaint ticket is raised automatically.
    customer_available_at = models.DateTimeField(null=True, blank=True)
    customer_available_note = models.CharField(max_length=200, null=True, blank=True)

    # Set by retrip_service.approve_retrip() on the SOURCE stop when it is
    # carried over to a continuation trip. Deliberately does not affect
    # `status` (still Pending/etc.) — see the comment in approve_retrip for
    # why the completion-percentage math depends on that.
    # DailyTripAssignment.unique_id as a plain string (no DB relation).
    carried_to_assignment_id = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
    )

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
        if self.customer_id:
            copy_flat_geo(self, self.customer)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_assignment_id}:customer:{self.customer_id}:{self.collection_type}"

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def trip_assignment(self):
        return self._lookup(
            "app.models.core_modules.daily_operations.daily_trip_assignment.DailyTripAssignment",
            self.trip_assignment_id,
        )

    @property
    def customer(self):
        return self._lookup(
            "app.models.masters.customer_masters.customercreation.CustomerCreation",
            self.customer_id,
        )

    @property
    def waste_collection(self):
        return self._lookup(
            "app.models.core_modules.daily_operations.waste_collection.WasteCollection",
            self.waste_collection_id,
        )

    @property
    def carried_to_assignment(self):
        return self._lookup(
            "app.models.core_modules.daily_operations.daily_trip_assignment.DailyTripAssignment",
            self.carried_to_assignment_id,
        )

    def mark_status(
        self, status, reason=None, latitude=None, longitude=None, evidence_image=None,
    ):
        """Mark this household/bulk stop Not Available / Collect Later from
        the operator app. No WasteCollection is created in that case."""
        self.status = status
        self.status_reason = reason
        self.status_latitude = latitude
        self.status_longitude = longitude
        self.status_evidence_image = evidence_image
        self.is_collected = False
        self.collected_at = None
        update_fields = [
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "status_evidence_image",
            "is_collected",
            "collected_at",
            "updated_at",
        ]
        if status == self.STATUS_MISSED:
            self.collected_weight_kg = None
            update_fields.append("collected_weight_kg")
        self.save(update_fields=update_fields)
        if status == self.STATUS_MISSED and self.customer_available_at:
            # The customer said they were home and it still ended Not
            # Available: put it on record as a Missed Pickup ticket.
            from app.services.customer_availability import raise_missed_pickup_ticket

            raise_missed_pickup_ticket(self)

    def mark_collected(self, waste_collection, collected_at=None):
        from decimal import Decimal
        self.waste_collection_id = getattr(
            waste_collection, "unique_id", waste_collection
        )
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
