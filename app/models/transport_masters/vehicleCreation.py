from django.db import models

from app.models.transport_masters.fuel import Fuel
from .vehicleTypeCreation import VehicleTypeCreation
from app.utils.comfun import generate_unique_id


def generate_vehicle_creation_id():
    return f"VEHCRE-{generate_unique_id()}"


def vehicle_rc_upload_path(instance, filename):
    return f"uploads/vehicles/rc/{instance.unique_id}_{filename}"


def vehicle_insurance_upload_path(instance, filename):
    return f"uploads/vehicles/insurance/{instance.unique_id}_{filename}"


class VehicleCreation(models.Model):
    class ConditionChoices(models.TextChoices):
        NEW = "NEW", "New"
        SECOND_HAND = "SECOND_HAND", "Second Hand"

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_vehicle_creation_id,
        editable=False,
    )

    fuel_type = models.ForeignKey(
        Fuel, on_delete=models.SET_NULL, null=True, blank=True
    )
    vehicle_type = models.ForeignKey(
        VehicleTypeCreation, on_delete=models.SET_NULL, null=True, blank=True
    )

    vehicle_no = models.CharField(max_length=50, unique=True)
    capacity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    mileage_per_liter = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    service_record = models.TextField(blank=True, null=True)
    vehicle_insurance = models.CharField(max_length=100, blank=True, null=True)
    insurance_expiry_date = models.DateField(blank=True, null=True)
    vehicle_condition = models.CharField(
        max_length=20,
        choices=ConditionChoices.choices,
        default=ConditionChoices.NEW,
    )
    fuel_tank_capacity = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    rc_upload = models.FileField(
        upload_to=vehicle_rc_upload_path, null=True, blank=True
    )
    vehicle_insurance_file = models.FileField(
        upload_to=vehicle_insurance_upload_path, null=True, blank=True
    )

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Vehicle Creation"
        verbose_name_plural = "Vehicle Creations"

    def __str__(self):
        return self.vehicle_no

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])
