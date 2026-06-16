from django.db import models
from app.utils.base_models import BaseMaster
from app.models.customers.customercreation import CustomerCreation
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project



def generate_wastecollection_id():
    """Generate readable prefixed ID, e.g., WASTE-20251028001"""
    return f"WASTE-{generate_unique_id()}"

class WasteCollection(BaseMaster):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )

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
        ward = self.customer.ward.ward_name if self.customer and self.customer.ward else ""
        zone = self.customer.zone.zone_name if self.customer and self.customer.zone else ""
        city = self.customer.city.city_name if self.customer and self.customer.city else ""
        panchayat = self.customer.panchayat.panchayat_name if self.customer and self.customer.panchayat else ""
        return f"{customer_name} - {ward or zone or city} - {panchayat}"

    def save(self, *args, **kwargs):
        """Auto-calculate total before save."""
        self.total_quantity = (
            (self.wet_waste or 0)
            + (self.dry_waste or 0)
            + (self.mixed_waste or 0)
        )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
