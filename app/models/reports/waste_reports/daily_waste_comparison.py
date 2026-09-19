from django.db import models
from app.models.masters.waste_masters.wastetype import WasteType
from app.utils.comfun import generate_unique_id

def generate_daily_waste_comparison_id():
    return f"DWC-{generate_unique_id()}"

class DailyWasteComparison(models.Model):
    unique_id = models.CharField(max_length=30, primary_key=True, default=generate_daily_waste_comparison_id, editable=False)
    collection_date = models.DateField()
    waste_type_id = models.ForeignKey(WasteType, on_delete=models.DO_NOTHING, db_column="waste_type_id", db_constraint=False)

    # Plain unique_id references (no ForeignKey/DB relation) — see
    # docs/geo_hierarchy_fk_removal.md. Existence of the referenced row is
    # checked at the API layer (see DailyWasteComparisonSerializer's
    # validate_<field> methods), not enforced by the database.
    state = models.CharField(max_length=30, null=True, blank=True, db_column="state_id")
    district = models.CharField(max_length=30, null=True, blank=True, db_column="district_id")
    area_type = models.CharField(max_length=30, null=True, blank=True, db_column="area_type_id")
    corporation = models.CharField(max_length=30, null=True, blank=True, db_column="corporation_id")
    municipality = models.CharField(max_length=30, null=True, blank=True, db_column="municipality_id")
    town_panchayat = models.CharField(max_length=30, null=True, blank=True, db_column="town_panchayat_id")
    panchayat_union = models.CharField(max_length=30, null=True, blank=True, db_column="panchayat_union_id")
    panchayat = models.CharField(max_length=30, null=True, blank=True, db_column="panchayat_id")

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
