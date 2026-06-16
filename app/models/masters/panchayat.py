from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.common_masters.state import State
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.masters.areatype import AreaType
from app.models.masters.block_panchayat_union import BlockPanchayatUnion

def generate_panchayat_id():
    return f"PANCHAYAT-{generate_unique_id()}"

class GeoFencingType(models.TextChoices):
    POLYGON = "polygon", "Polygon"
    CIRCLE = "circle", "Circle"
    RECTANGLE = "rectangle", "Rectangle"
    SQUARE = "square", "Square"


class WeightUnit(models.TextChoices):
    KG = "kg", "Kg"
    TONNE = "tonne", "Tonne"


class Panchayat(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_panchayat_id,
        editable=False
    )

    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="pancahyat",
        db_column="company_id",
    )

    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="pancahyat",
        db_column="project_id",
    )

    state_id = models.ForeignKey(
        State,
        on_delete = models.PROTECT,
        related_name="panchayat",
        db_column="state_id",
        
    )

    city_id = models.ForeignKey(
        City,
        on_delete = models.PROTECT,
        related_name="panchayat",
        db_column="city_id",
        
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
        limit_choices_to={"name": "Rural"},
        null=True,
        blank=True
    )

    hierarchy_id = models.ForeignKey(
        AdministrativeHierarchy,
        on_delete=models.PROTECT,
        limit_choices_to={"level_name": "Panchayat"},
        null=True,
        blank=True
    )

    geofencing_type = models.CharField(
        max_length=20,
        choices=GeoFencingType.choices,
        default=GeoFencingType.SQUARE
    )
    panchayat_name = models.CharField(max_length=100)
    agreed_weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Monthly agreed collection weight in kg",
    )
    weight_unit = models.CharField(
        max_length=10,
        choices=WeightUnit.choices,
        default=WeightUnit.KG,
        help_text="Unit for agreed weight",
    )
    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text="Date from which this agreed weight is valid",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True)

    block_id = models.ForeignKey(
        BlockPanchayatUnion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="panchayats",
        db_column="block_id",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
