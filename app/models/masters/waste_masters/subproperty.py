from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .property import Property
from app.utils import ref_cache



def generate_subproperty_id():
    return f"SUBPROPERTY-{generate_unique_id()}"


class SubProperty(BaseMaster):

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        unique=True,
        default=generate_subproperty_id,
        editable=False
    )

    # Plain Property unique_id (no DB relation).
    property_id = models.CharField(max_length=40, db_column="property_id", db_index=True)

    sub_property_name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Sub Property"
        verbose_name_plural = "Sub Properties"
        ordering = ["sub_property_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["property_id", "sub_property_name", "is_deleted"],
                name="unique_sub_property_per_property_not_deleted"
            )
        ]

    @property
    def property_ref(self):
        return ref_cache.get(Property, self.property_id, "unique_id")

    def __str__(self):
        return f"{self.sub_property_name} ({getattr(self.property_ref, 'property_name', '')})"

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])