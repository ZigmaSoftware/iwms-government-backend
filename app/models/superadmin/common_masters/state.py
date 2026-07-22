from django.db import models
from app.utils.base_models import BaseMaster
from .country import Country
from .continent import Continent
from app.utils.comfun import generate_unique_id


def generate_state_id():
    return f"STATE-{generate_unique_id()}"


class State(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_state_id
    )

    country_id = models.ForeignKey(
        Country,
        on_delete=models.PROTECT,
        related_name="states",
        to_field="unique_id",
        db_column="country_id",
    )

    continent_id = models.ForeignKey(
        Continent,
        on_delete=models.PROTECT,
        related_name="states",
        to_field="unique_id",
        db_column="continent_id",
    )

    name = models.CharField(max_length=100)
    label = models.CharField(max_length=20, blank=True, null=True)
    coordinates = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("country_id", "name")

    def __str__(self):
        return f"{self.name} ({self.country_id.name})"

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])
