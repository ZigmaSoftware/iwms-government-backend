from django.db import models
from app.utils.base_models import BaseMaster
from .continent import Continent
from app.utils.comfun import generate_unique_id


def generate_country_id():
    return f"COUNTRY-{generate_unique_id()}"


class Country(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_country_id
    )

    continent_id = models.ForeignKey(
        Continent,
        on_delete=models.PROTECT,
        related_name="countries",
        to_field="unique_id",
        db_column="continent_id",
    )

    name = models.CharField(max_length=100)
    currency = models.CharField(max_length=20, blank=True, null=True)
    mob_code = models.CharField(max_length=5, blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
