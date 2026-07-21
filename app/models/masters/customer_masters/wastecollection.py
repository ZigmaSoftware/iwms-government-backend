from django.db import models
from app.utils.base_models import BaseMaster
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.utils.comfun import generate_unique_id
from app.utils.hierarchy import copy_flat_geo



def generate_wastecollection_id():
    """Generate readable prefixed ID, e.g., WASTE-20251028001"""
    return f"WASTE-{generate_unique_id()}"

class WasteCollection(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_wastecollection_id,
        editable=False,
    )

    #  Link one customer – all details fetched via relation
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        related_name="waste_collections"
    )

    # Optional link to the trip assignment that triggered this collection
    trip_assignment_id = models.ForeignKey(
        DailyTripAssignment,
        on_delete=models.PROTECT,
        to_field="unique_id",
        related_name="waste_collections",
        db_column="trip_assignment_id",
        null=True,
        blank=True,
    )

    # Geography (flat FKs, mirroring CustomerCreation). Auto-inherited from the
    # linked household on save when left blank, but selectable/editable so a
    # collection can be scoped independently.
    state = models.ForeignKey(
        State, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="waste_collections", to_field="unique_id", db_column="state_id",
    )
    district = models.ForeignKey(
        District, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="waste_collections", to_field="unique_id", db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="waste_collections", to_field="unique_id", db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="waste_collections", to_field="unique_id", db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="waste_collections", to_field="unique_id", db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="waste_collections", to_field="unique_id", db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="waste_collections", to_field="unique_id", db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="waste_collections", to_field="unique_id", db_column="panchayat_id",
    )

    #  Waste details
    wet_waste = models.FloatField(default=0.0)
    dry_waste = models.FloatField(default=0.0)
    mixed_waste = models.FloatField(default=0.0)
    total_quantity = models.FloatField(default=0.0)

    # Optional: collection timestamp
    collection_date = models.DateField(auto_now_add=True)
    collection_time = models.TimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Waste Collection"
        verbose_name_plural = "Waste Collections"
        ordering = ["-collection_date", "-collection_time"]

    def __str__(self):
        """Readable entry with linked customer and location."""
        customer_name = self.customer.customer_name if self.customer else "Unknown"
        district = getattr(getattr(self.customer, "district", None), "name", "") if self.customer else ""
        panchayat = getattr(getattr(self.customer, "panchayat_id", None), "panchayat_name", "") if self.customer else ""
        return f"{customer_name} - {panchayat or district}"

    def save(self, *args, **kwargs):
        """Auto-calculate total and inherit geography from the household."""
        self.total_quantity = (
            (self.wet_waste or 0)
            + (self.dry_waste or 0)
            + (self.mixed_waste or 0)
        )
        # If no geography was supplied, copy the household's flat geo FKs so the
        # record is always scoped even when created via seeders/admin/API.
        if self.customer_id and not self.district_id:
            copy_flat_geo(self, self.customer, only_empty=True)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
