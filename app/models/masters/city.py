from django.db import models
from app.models.superadmin_masters.company import Company
from app.utils.base_models import BaseMaster
from ..common_masters.country import Country
from ..common_masters.state import State
from .district import District
from ..common_masters.continent import Continent
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.project import Project



def generate_city_id():
    return f"CITY-{generate_unique_id()}"


class City(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_city_id
    )

    continent_id = models.ForeignKey(
        Continent,
        on_delete=models.PROTECT,
        related_name="cities",
        db_column="continent_id",
    )

    country_id = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="cities",
        db_column="country_id",
    )

    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="cities",
        db_column="state_id",
    )

    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="cities",
        db_column="district_id",
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    company_id=models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="cities",
        db_column="company_id",
    )
    project_id=models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="cities",
        db_column="project_id",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.state_id.name})"

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
