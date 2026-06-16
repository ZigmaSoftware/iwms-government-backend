# Compatibility shim — model lives in schedule_masters
from app.models.schedule_masters.monthly_weight_report import (
    MonthlyWeightReport,
    generate_monthlyweightreport_id,
)

__all__ = ["MonthlyWeightReport", "generate_monthlyweightreport_id"]
