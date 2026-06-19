from django.db import models
from app.utils.base_models import BaseMaster
from ..common_masters.country import Country
from ..common_masters.state import State
from ..common_masters.continent import Continent
from app.utils.comfun import generate_unique_id



def generate_district_id():
    return f"DIST-{generate_unique_id()}"

class District(BaseMaster):


    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_district_id
    )

    country_id = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="unique_id",
        db_column="country_id",
    )

    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="unique_id",
        db_column="state_id",
    )

    continent_id = models.ForeignKey(
        Continent,
        on_delete=models.PROTECT,
        related_name="districts",
        to_field="unique_id",
        db_column="continent_id",
    )

    name = models.CharField(max_length=100)
    district_code = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("state_id", "name")   # FIXED

    def __str__(self):
        return f"{self.name} ({self.state_id.name})"
