from django.db import models
from app.models.masters.panchayat import Panchayat
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.user_creations.waste_collection_bluetooth import WasteType
from app.utils.comfun import generate_unique_id

def generate_daily_waste_comparison_id():
    return f"DWC-{generate_unique_id()}"

class DailyWasteComparison(models.Model):
    unique_id = models.CharField(max_length=30, primary_key=True, default=generate_daily_waste_comparison_id, editable=False)
    company_id = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="daily_waste_comparisons", db_column="company_id", null=True, blank=True)
    project_id = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="daily_waste_comparisons", db_column="project_id", null=True, blank=True)
    panchayat_id = models.ForeignKey(Panchayat, on_delete=models.DO_NOTHING, db_column="panchayat_id", db_constraint=False)
    collection_date = models.DateField()
    waste_type_id = models.ForeignKey(WasteType, on_delete=models.DO_NOTHING, db_column="waste_type_id", db_constraint=False)
    agreed_weight_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    actual_weight_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    variance_kg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    variance_percent = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    report_status = models.CharField(max_length=50, blank=True, null=True)
    total_trips = models.PositiveIntegerField(default=0)
    collection_points_covered = models.PositiveIntegerField(default=0)

    class Meta:
        managed = True
        db_table = "daily_waste_comparison"
        ordering = ["-collection_date"]
        indexes = [
            models.Index(fields=["collection_date", "panchayat_id"]),
            models.Index(fields=["company_id", "project_id", "collection_date"]),
        ]
