from django.db import models

from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.utils.comfun import generate_unique_id

def generate_monthlyweightreport_id():
    return f"MWR-{generate_unique_id()}"


class MonthlyWeightReport(models.Model):

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_monthlyweightreport_id,
        editable=False,
    )
    location_node = models.ForeignKey(
        "app.HierarchyNode",
        on_delete=models.DO_NOTHING,
        db_column="location_node_id",
        db_constraint=False,
    )
    month = models.CharField(max_length=20)
    waste_type_id = models.ForeignKey(
        WasteType,
        on_delete=models.DO_NOTHING,
        db_column="waste_type_id",
        db_constraint=False,
    )
    agreed_weight_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    actual_weight_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    variance_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    variance_percent = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    report_status = models.CharField(max_length=50, blank=True, null=True)
    total_trips = models.PositiveIntegerField(default=0)
    collection_points_covered = models.PositiveIntegerField(default=0)

    class Meta:
        managed = True
        db_table = "monthly_weight_report"
