from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.areatype import AreaType
from django.db.models import Max


def generate_hierarchy_id():
    return f"HIER-{generate_unique_id()}"


class AdministrativeHierarchy(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_hierarchy_id,
        editable=False
    )

    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.PROTECT,
        related_name="hierarchies"
    )

    level_name = models.CharField(max_length=50)
    # Zone / Ward / Panchayat

    hierarchy_order = models.PositiveIntegerField(editable=False)

    class Meta:
        ordering = ["hierarchy_order"]
        unique_together = ("area_type", "level_name")

    def save(self, *args, **kwargs):
        if not self.hierarchy_order:
            last_order = (
                AdministrativeHierarchy.objects
                .filter(area_type=self.area_type)
                .aggregate(Max("hierarchy_order"))
                .get("hierarchy_order__max")
            )

            self.hierarchy_order = (last_order or 0) + 1

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.area_type.name} - {self.level_name}"