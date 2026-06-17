from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id

def generate_vehicle_type_id():
    """Generate a unique ID prefixed with VHTYPE."""
    return f"VHTYPE-{generate_unique_id()}"
class VehicleTypeCreation(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_vehicle_type_id,
        editable=False
    )
    vehicleType = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    class Meta:
        ordering = ["unique_id"]
        verbose_name = "Vehicle Type"
        verbose_name_plural = "Vehicle Types"

    def __str__(self):
        return self.vehicleType

    def delete(self, *args, **kwargs):
        """
        Soft delete: mark this vehicle type as inactive (and optionally cascade).
        """
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])
