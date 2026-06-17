from django.db import models
from app.utils.comfun import generate_unique_id
from app.utils.base_models import BaseMaster
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.common_masters.state import State


def generate_area_type_id():
    return f"AREA-{generate_unique_id()}"

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

    city_id = models.ForeignKey(
        City,
        on_delete = models.PROTECT,
        related_name="area_type",
        db_column="city_id",
        
    )

    district_id = models.ForeignKey(
        District,
        on_delete = models.PROTECT,
        related_name="area_type",
        db_column="district_id",
        
    )


    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name