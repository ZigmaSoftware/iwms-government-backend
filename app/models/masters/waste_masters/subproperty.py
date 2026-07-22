from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from .property import Property



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

    property_id = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="sub_properties",
        to_field="unique_id"
    )

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

    def __str__(self):
        return f"{self.sub_property_name} ({self.property_id.property_name})"  # FIXED

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])