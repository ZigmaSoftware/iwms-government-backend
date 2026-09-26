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
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)

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
