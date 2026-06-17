from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.panchayat import Panchayat
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.common_masters.state import State
from django.core.exceptions import ValidationError

def geneate_collection_point_id():
    return f"CP-{generate_unique_id()}"

class Collection_point(BaseMaster):
    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=geneate_collection_point_id,
        editable=False
    )



    state_id = models.ForeignKey(
        State,
        on_delete = models.PROTECT,
        related_name="cp",
        db_column="state_id",
        
    )

    city_id = models.ForeignKey(
        City,
        on_delete = models.PROTECT,
        related_name="cp",
        db_column="city_id",
        
    )

    district_id = models.ForeignKey(
        District,
        on_delete = models.PROTECT,
        related_name="cp",
        db_column="district_id",
        
    )


    panchayat_id = models.ForeignKey(
        Panchayat,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="panchayat_id",
        null=True,
        blank=True
    )

    ward_id = models.ForeignKey(
        Ward,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="ward_id",
        null=True,
        blank=True
    )

    cp_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



    def clean(self):
        if not self.panchayat_id and not self.ward_id:
            raise ValidationError("Collection Point must belong to Ward or Panchayat.")

        if self.panchayat_id and self.ward_id:
            raise ValidationError("Collection Point cannot belong to both Ward and Panchayat.")
        

    def __str__(self):
        if self.panchayat_id:
            return f"{self.cp_name} (Panchayat: {self.panchayat_id.panchayat_name})"

        if self.ward_id:
            return f"{self.cp_name} (Ward: {self.ward_id.ward_name})"

        return self.cp_name