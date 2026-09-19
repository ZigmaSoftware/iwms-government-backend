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

    # Plain unique_id reference (no ForeignKey/DB relation) — see
    # docs/geo_hierarchy_fk_removal.md. area_type is looked up explicitly
    # via AreaType.objects.filter(unique_id=self.area_type) where needed.
    area_type = models.CharField(max_length=30, db_column="area_type_id")

    level_name = models.CharField(max_length=50)
    # Local body / Panchayat

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
        area_type_name = (
            AreaType.objects.filter(unique_id=self.area_type)
            .values_list("name", flat=True)
            .first()
        )
        return f"{area_type_name or self.area_type} - {self.level_name}"
