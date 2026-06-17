from django.db import models
from app.utils.base_models import BaseMaster
from django.core.validators import RegexValidator
from ..common_masters.continent import Continent
from ..common_masters.country import Country
from ..common_masters.state import State
from .district import District
from .city import City
from app.utils.comfun import generate_unique_id
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.masters.areatype import AreaType



# ----------------------------------
# ID GENERATOR
# ----------------------------------
def generate_zone_id():
    return f"ZONE-{generate_unique_id()}"


# ----------------------------------
# ENUMS
# ----------------------------------
class GeoFencingType(models.TextChoices):
    POLYGON = "polygon", "Polygon"
    CIRCLE = "circle", "Circle"
    RECTANGLE = "rectangle", "Rectangle"
    SQUARE = "square", "Square"





# ----------------------------------
# VALIDATORS
# ----------------------------------
hex_color_validator = RegexValidator(
    regex=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
    message="Invalid HEX color code"
)



class Zone(BaseMaster):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_zone_id,
        editable=False
    )


    state_id = models.ForeignKey(State, on_delete=models.PROTECT)
    district_id = models.ForeignKey(District, on_delete=models.PROTECT)
    city_id = models.ForeignKey(City, on_delete=models.PROTECT)

    area_type_id = models.ForeignKey(
        AreaType,
        on_delete=models.PROTECT,
        limit_choices_to={"name": "Urban"},
        null=True,
        blank=True
    )

    hierarchy_id = models.ForeignKey(
        AdministrativeHierarchy,
        on_delete=models.PROTECT,
        limit_choices_to={"level_name": "Zone"},
        null=True,
        blank=True
    )

    zone_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6,null=True,blank=True)
    coordinates = models.JSONField(default=list, blank=True)
    geofencing_type = models.CharField(max_length=20, choices=GeoFencingType.choices, default=GeoFencingType.SQUARE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)     
    
    
