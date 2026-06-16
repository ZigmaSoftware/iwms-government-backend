from django.db import models
from django.core.exceptions import ValidationError
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project



def generate_userchargerule_id():
    """Generate readable prefixed ID, e.g., UCR-20251028001"""
    return f"UCR-{generate_unique_id()}"

class UserChargeRule(BaseMaster):
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
        default=generate_userchargerule_id,
        editable=False,
    )

    property_id = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="user_charge_rules",
        to_field="unique_id",
        db_column="property_id",
    )

    subproperty_id = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        related_name="user_charge_rules",
        to_field="unique_id",
        db_column="subproperty_id",
    )

    min_sqmtr_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    max_sqmtr_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    charge_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    is_bulk_waste_generator = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "User Charge Rule"
        verbose_name_plural = "User Charge Rules"
        ordering = ["unique_id"]

    def __str__(self):
        if self.is_bulk_waste_generator:
            slab_text = "Bulk Generator (fixed pricing)"
        else:
            slab_text = f"{self.min_sqmtr_value} to {self.max_sqmtr_value} sq.mtr"

        return f"{self.unique_id} - {slab_text} - {self.charge_amount}"

    def clean(self):
        errors = {}

        if self.charge_amount is None:
            errors["charge_amount"] = "Amount is required."

        if self.is_bulk_waste_generator:
            if self.min_sqmtr_value is not None:
                errors["min_sqmtr_value"] = (
                    "Must be null when is_bulk_waste_generator is true."
                )

            if self.max_sqmtr_value is not None:
                errors["max_sqmtr_value"] = (
                    "Must be null when is_bulk_waste_generator is true."
                )

        else:
            if self.min_sqmtr_value is None:
                errors["min_sqmtr_value"] = (
                    "This field is required when is_bulk_waste_generator is false."
                )

            if self.max_sqmtr_value is None:
                errors["max_sqmtr_value"] = (
                    "This field is required when is_bulk_waste_generator is false."
                )

            if (
                self.min_sqmtr_value is not None
                and self.max_sqmtr_value is not None
                and self.min_sqmtr_value >= self.max_sqmtr_value
            ):
                errors["non_field_errors"] = (
                    "min_sqmtr_value must be less than max_sqmtr_value."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields:
            update_set = set(update_fields)
            if update_set.issubset({"is_deleted", "is_active", "updated_by"}):
                return super().save(*args, **kwargs)

        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])

    @property
    def is_authenticated(self):
        """
        Always return True for authenticated users.
        Required by Django REST Framework's permission system.
        """
        return True
