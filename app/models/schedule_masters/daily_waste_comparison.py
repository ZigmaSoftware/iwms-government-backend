from django.db import models
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.assets.wastetype import WasteType
from app.utils.comfun import generate_unique_id

def generate_daily_waste_comparison_id():
    return f"DWC-{generate_unique_id()}"

class DailyWasteComparison(models.Model):
    unique_id = models.CharField(max_length=30, primary_key=True, default=generate_daily_waste_comparison_id, editable=False)
    collection_date = models.DateField()
    waste_type_id = models.ForeignKey(WasteType, on_delete=models.DO_NOTHING, db_column="waste_type_id", db_constraint=False)

    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_waste_comparisons",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_waste_comparisons",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_waste_comparisons",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_waste_comparisons",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_waste_comparisons",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_waste_comparisons",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_waste_comparisons",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_waste_comparisons",
        to_field="unique_id",
        db_column="panchayat_id",
    )

    actual_weight_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_trips = models.PositiveIntegerField(default=0)
    collection_points_covered = models.PositiveIntegerField(default=0)

    class Meta:
        managed = True
        db_table = "daily_waste_comparison"
        ordering = ["-collection_date"]
        indexes = [
            models.Index(fields=["collection_date", "panchayat"]),
        ]
