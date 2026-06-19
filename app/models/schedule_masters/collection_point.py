from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.panchayat import Panchayat
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.district import District
from app.models.common_masters.state import State
from django.core.exceptions import ValidationError
from app.utils.hierarchy import HIERARCHY_FIELDS, HIERARCHY_LABELS, selected_hierarchy_values

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
    corporation_id = models.ForeignKey(
        Corporation,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="corporation_id",
        null=True,
        blank=True,
    )
    municipality_id = models.ForeignKey(
        Municipality,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="municipality_id",
        null=True,
        blank=True,
    )
    town_panchayat_id = models.ForeignKey(
        TownPanchayat,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="town_panchayat_id",
        null=True,
        blank=True,
    )
    panchayat_union_id = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.PROTECT,
        related_name="cp",
        db_column="panchayat_union_id",
        null=True,
        blank=True,
    )

    cp_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



    def clean(self):
        if len(selected_hierarchy_values(self)) != 1:
            raise ValidationError("Collection Point must belong to exactly one hierarchy level.")
        

    def __str__(self):
        for field in HIERARCHY_FIELDS:
            value = getattr(self, field, None)
            if value:
                return f"{self.cp_name} ({HIERARCHY_LABELS[field]}: {value})"

        return self.cp_name
