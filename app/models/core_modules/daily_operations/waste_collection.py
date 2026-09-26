from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo
from app.utils import ref_cache



def generate_wastecollection_id():
    """Generate readable prefixed ID, e.g., WASTE-20251028001"""
    return f"WASTE-{generate_unique_id()}"

class WasteCollection(BaseMaster):
    # Same vocabulary as DailyTripHouseholdCollection.STATUS_CHOICES
    # (app/models/schedule_masters/daily_trip_household_collection.py), the
    # canonical household-stop status used across the app.
    STATUS_PENDING = "Pending"
    STATUS_COLLECTED = "Collected"
    STATUS_NOT_AVAILABLE = "Not Available"
    STATUS_COLLECT_LATER = "Collect Later"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COLLECTED, "Collected"),
        (STATUS_NOT_AVAILABLE, "Not Available"),
        (STATUS_COLLECT_LATER, "Collect Later"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_wastecollection_id,
        editable=False,
    )

    # Link one customer — plain unique_id string (no DB relation), same as
    # CustomerCreation's own geo convention.
    customer_id = models.CharField(max_length=30, db_index=True)

    # Optional link to the trip assignment that triggered this collection —
    # DailyTripAssignment.unique_id as a plain string (no DB relation).
    trip_assignment_id = models.CharField(
        max_length=50, null=True, blank=True, db_index=True,
    )

    # Geography (flat plain-string FKs, mirroring CustomerCreation/Ward — no
    # DB relation/join, holding the related row's unique_id). Auto-inherited
    # from the linked household on save when left blank, but
    # selectable/editable so a collection can be scoped independently.
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    ward_id = models.CharField(max_length=30, null=True, blank=True, db_index=True)

    #  Waste details
    wet_waste = models.FloatField(default=0.0)
    dry_waste = models.FloatField(default=0.0)
    mixed_waste = models.FloatField(default=0.0)
    sanitary_waste = models.FloatField(default=0.0)
    total_quantity = models.FloatField(default=0.0)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    # Collection date is now a plain, user-editable field (matching
    # BinCollectionEvent.collection_date) rather than auto-set on creation.
    collection_date = models.DateField()
    collection_time = models.TimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Waste Collection"
        verbose_name_plural = "Waste Collections"
        ordering = ["-collection_date", "-collection_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer_id", "trip_assignment_id"],
                condition=models.Q(is_deleted=False),
                name="unique_customer_trip_not_deleted",
            ),
        ]

    def __str__(self):
        """Readable entry with linked customer and location."""
        from app.models.masters.district import District
        from app.models.masters.panchayat import Panchayat

        customer_name = self.customer.customer_name if self.customer else "Unknown"
        district = (
            District.objects.filter(unique_id=self.customer.district_id)
            .values_list("name", flat=True)
            .first()
            if self.customer else ""
        )
        panchayat = (
            Panchayat.objects.filter(unique_id=self.customer.panchayat_id)
            .values_list("panchayat_name", flat=True)
            .first()
            if self.customer else ""
        )
        return f"{customer_name} - {panchayat or district or ''}"

    def save(self, *args, **kwargs):
        """Auto-calculate total and inherit geography from the household."""
        self.total_quantity = (
            (self.wet_waste or 0)
            + (self.dry_waste or 0)
            + (self.mixed_waste or 0)
            + (self.sanitary_waste or 0)
        )
        # If no geography was supplied, copy the household's flat geo FKs so the
        # record is always scoped even when created via seeders/admin/API.
        if self.customer_id and not self.district_id:
            copy_flat_geo(self, self.customer, only_empty=True)
        if self.customer_id and not self.ward_id:
            self.ward_id = getattr(self.customer, "ward_id", None)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def customer(self):
        return self._lookup(
            "app.models.masters.customer_masters.customercreation.CustomerCreation",
            self.customer_id,
        )

    @property
    def trip_assignment(self):
        return self._lookup(
            "app.models.core_modules.daily_operations.daily_trip_assignment.DailyTripAssignment",
            self.trip_assignment_id,
        )

    @property
    def ward(self):
        return self._lookup(
            "app.models.masters.ward.Ward", self.ward_id
        )
