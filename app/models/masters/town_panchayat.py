from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.district import District
from app.models.common_masters.state import State
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.masters.areatype import AreaType


def generate_town_panchayat_id():
    return f"TWNP-{generate_unique_id()}"


class GeoFencingType(models.TextChoices):
    POLYGON = "polygon", "Polygon"
    CIRCLE = "circle", "Circle"
    RECTANGLE = "rectangle", "Rectangle"
    SQUARE = "square", "Square"


class TownPanchayat(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_town_panchayat_id,
        editable=False,
    )


    state_id = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="town_panchayats",
        db_column="state_id",
    )
    district_id = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        related_name="town_panchayats",
        db_column="district_id",
    )

    area_type_id = models.ForeignKey(
        AreaType,
        on_delete=models.PROTECT,
        limit_choices_to={"name": "Urban"},
        null=True,
        blank=True,
    )
    hierarchy_id = models.ForeignKey(
        AdministrativeHierarchy,
        on_delete=models.PROTECT,
        limit_choices_to={"level_name": "Town Panchayat"},
        null=True,
        blank=True,
    )

    town_panchayat_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    geofencing_type = models.CharField(
        max_length=20,
        choices=GeoFencingType.choices,
        default=GeoFencingType.SQUARE,
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["town_panchayat_name"]
