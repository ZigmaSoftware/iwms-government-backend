from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_continent_id():
    return f"CONT-{generate_unique_id()}"


class Continent(BaseMaster):

    CASCADE_SOFT_DELETE = ("countries", "states", "districts")
    CACHE_SCOPES = ("continent_list", "continent_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_continent_id
    )

    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
