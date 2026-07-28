from django.db import models
from app.utils.comfun import generate_unique_id
from app.utils.base_models import BaseMaster
from app.models.masters.district import District
from app.models.superadmin.common_masters.state import State


def generate_area_type_id():
    return f"AREA-{generate_unique_id()}"

class AreaTypeName(models.TextChoices):
    URBAN_LOCAL_BODY = "Urban Local Body", "Urban Local Body"
    RURAL_LOCAL_BODY = "Rural Local Body", "Rural Local Body"

class AreaType(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_area_type_id,
        editable=False
    )

    state_id = models.ForeignKey(
        State,
        on_delete = models.PROTECT,
        related_name="area_type",
        db_column="state_id",
        
    )

    district_id = models.ForeignKey(
        District,
        on_delete = models.PROTECT,
        related_name="area_type",
        db_column="district_id",
        
    )

    name = models.CharField(max_length=50, choices=AreaTypeName.choices)
    coordinates = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("state_id", "district_id", "name")

    def __str__(self):
        return self.name
