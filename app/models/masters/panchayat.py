from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.district import District
from app.models.common_masters.state import State
from app.models.masters.areatype import AreaType

def generate_panchayat_id():
    return f"PANCHAYAT-{generate_unique_id()}"

class Panchayat(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_panchayat_id,
        editable=False
    )



    state_id = models.ForeignKey(
        State,
        on_delete = models.PROTECT,
        related_name="panchayat",
        db_column="state_id",
        
    )

    district_id = models.ForeignKey(
        District,
        on_delete = models.PROTECT,
        related_name="panchayat",
        db_column="district_id",
    )

    area_type_id = models.ForeignKey(
        AreaType,
        on_delete=models.PROTECT,
        related_name="panchayats",
        db_column="area_type_id",
        null=True,
        blank=True,
    )

    panchayat_name = models.CharField(max_length=100)
    agreed_weight_kg = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, null=True, blank=True
    )
    coordinates = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["panchayat_name"]
        unique_together = ("state_id", "district_id", "area_type_id", "panchayat_name")
