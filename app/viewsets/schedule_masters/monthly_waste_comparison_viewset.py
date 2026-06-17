"""
Monthly Waste Comparison — computed live from DailyTripLog.

Data source: DailyTripLog (Submitted + Verified logs only)
  actual_weight_kg  = Sum(collected_weight_kg) per (month, panchayat, waste_type)
                      OR household_collected_weight_kg when source=household
                      OR both combined when source=all
  agreed_weight_kg  = Panchayat.agreed_weight_kg × COUNT(DISTINCT trip_date)
  total_trips       = Count of trip logs in the group
  points_covered    = Count of distinct collection_point_id in the group

Query params:
  source  bin (default) | household | all
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Sum, F, ExpressionWrapper, DecimalField, Value
from django.db.models.functions import Coalesce
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.monthly_weight_report import MonthlyWeightReport
from app.serializers.schedule_masters.monthly_weight_report_serializer import MonthlyWeightReportSerializer
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")


def decimal_value(value):
    if value is None:
        return ZERO
    return Decimal(str(value))


def rounded(value):
    return decimal_value(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def percent(numerator, denominator):
    d = decimal_value(denominator)
    if d == ZERO:
        return ZERO
    return rounded(decimal_value(numerator) / d * Decimal("100"))


def variance_pct(actual, agreed):
    agreed_d = decimal_value(agreed)
    if agreed_d == ZERO:
        return ZERO
    return rounded((decimal_value(actual) - agreed_d) / agreed_d * Decimal("100"))


def performance_status(actual, agreed):
    actual = decimal_value(actual)
    agreed = decimal_value(agreed)
    if actual > agreed:
        return "Surplus"
    if actual < agreed:
        return "Deficit"
    return "On Target"


class MonthlyWasteComparisonReportViewSet(CompanyScopedViewSet):
    permission_resource = "MonthlyWasteComparisonReport"
    # Keep original queryset for retrieve/update/delete operations
    queryset = MonthlyWeightReport.objects.select_related(
        "panchayat_id", "waste_type_id"
    )
    serializer_class = MonthlyWeightReportSerializer
    lookup_field = "unique_id"

    def list(self, request):
        # ── base queryset: only confirmed trip logs ──────────────────────
        queryset = DailyTripLog.objects.select_related(
            "panchayat_id", "waste_type_id",
        ).filter(
            is_deleted=False,
            log_status__in=[
                DailyTripLog.LOG_STATUS_SUBMITTED,
                DailyTripLog.LOG_STATUS_VERIFIED,
            ],
        )

        queryset = self.filter_queryset(queryset)

        # ── month / panchayat / waste_type filters ───────────────────────
        month_param = request.query_params.get("month")
        panchayat_param = request.query_params.get("panchayat_id")
        waste_type_param = request.query_params.get("waste_type_id")

        if month_param:
            try:
                year, mon = month_param.split("-")
                queryset = queryset.filter(
                    trip_date__year=int(year),
                    trip_date__month=int(mon),
                )
            except (ValueError, AttributeError):
                pass

        if panchayat_param:
            queryset = queryset.filter(panchayat_id=panchayat_param)
        if waste_type_param:
            queryset = queryset.filter(waste_type_id=waste_type_param)

        # ── choose weight source ─────────────────────────────────────────
        source = request.query_params.get("source", "bin").lower()
        if source == "household":
            weight_field = "household_collected_weight_kg"
        elif source == "all":
            weight_field = None
        else:
            weight_field = "collected_weight_kg"

        # ── aggregate by (year, month, panchayat, waste_type) ────────────
        annotation_kwargs = {
            "total_trips": Count("unique_id"),
            "collection_points_covered": Count("collection_point_id", distinct=True),
            "distinct_trip_days": Count("trip_date", distinct=True),
        }
        if weight_field:
            annotation_kwargs["total_actual_weight"] = Sum(weight_field)
        else:
            annotation_kwargs["total_actual_weight"] = Sum(
                ExpressionWrapper(
                    Coalesce(F("collected_weight_kg"), Value(0, output_field=DecimalField()))
                    + Coalesce(F("household_collected_weight_kg"), Value(0, output_field=DecimalField())),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )

        grouped_qs = queryset.values(
            "trip_date__year",
            "trip_date__month",
            "panchayat_id",
            "panchayat_id__panchayat_name",
            "panchayat_id__agreed_weight_kg",
            "waste_type_id",
            "waste_type_id__waste_type_name",
        ).annotate(**annotation_kwargs)

        rows = []
        for row in grouped_qs:
            year_val  = row["trip_date__year"]
            month_val = row["trip_date__month"]
            month_str = f"{year_val}-{month_val:02d}"

            # Monthly agreed = daily target × number of trip-days this month
            agreed_per_day = decimal_value(row["panchayat_id__agreed_weight_kg"])
            trip_days      = int(row["distinct_trip_days"] or 0)
            agreed         = agreed_per_day * Decimal(str(trip_days))

            actual      = decimal_value(row["total_actual_weight"])
            variance    = actual - agreed
            total_trips = int(row["total_trips"] or 0)
            points      = int(row["collection_points_covered"] or 0)

            unique_id = (
                f"MWR-{month_str}-{row['panchayat_id']}-{row['waste_type_id']}"
            )

            rows.append({
                "unique_id": unique_id,
                "month": month_str,
                "panchayat_id": row["panchayat_id"],
                "panchayat_name": (
                    row["panchayat_id__panchayat_name"] or row["panchayat_id"]
                ),
                "waste_type_id": row["waste_type_id"],
                "waste_type": (
                    row["waste_type_id__waste_type_name"] or row["waste_type_id"]
                ),
                "total_agreed_weight": float(rounded(agreed)),
                "total_actual_weight": float(rounded(actual)),
                "variance_kg": float(rounded(variance)),
                "variance_percent": float(variance_pct(actual, agreed)),
                "report_status": performance_status(actual, agreed),
                "total_trips": total_trips,
                "collection_points_covered": points,
                "collection_efficiency_percent": float(percent(actual, agreed)),
                "coverage_efficiency_percent": float(percent(points, total_trips)),
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(total_trips)) if total_trips else ZERO
                ),
            })

        sort_mode = request.query_params.get("sort", "absolute").lower()
        if sort_mode == "deficit":
            rows.sort(key=lambda r: r["variance_kg"])
        elif sort_mode == "surplus":
            rows.sort(key=lambda r: r["variance_kg"], reverse=True)
        else:
            rows.sort(key=lambda r: abs(r["variance_kg"]), reverse=True)

        return Response({
            "source": source,
            "results": rows,
            "monthly_trends": self._build_monthly_trends(rows),
            "panchayat_comparison": self._build_panchayat_comparison(rows),
            "kpis": self._build_totals(rows),
        })

    # ── analytics helpers ────────────────────────────────────────────────

    def _build_monthly_trends(self, rows):
        # total_agreed_weight per row = daily_agreed × trip_days for that (month, panchayat, waste_type).
        # Since agreed_weight_kg is the panchayat's TOTAL daily target (across all waste types),
        # count it once per (month, panchayat) pair — not once per waste-type row.
        trends = {}
        seen_agreed = set()
        for row in rows:
            m = row["month"]
            trends.setdefault(m, {
                "month": m,
                "total_agreed_weight": 0.0, "total_actual_weight": 0.0,
                "total_trips": 0, "collection_points_covered": 0,
            })
            trends[m]["total_actual_weight"]       += row["total_actual_weight"]
            trends[m]["total_trips"]               += row["total_trips"]
            trends[m]["collection_points_covered"] += row["collection_points_covered"]

            key = (m, row["panchayat_id"])
            if key not in seen_agreed:
                seen_agreed.add(key)
                trends[m]["total_agreed_weight"] += row["total_agreed_weight"]

        result = []
        for item in sorted(trends.values(), key=lambda x: str(x["month"])):
            agreed = Decimal(str(item["total_agreed_weight"]))
            actual = Decimal(str(item["total_actual_weight"]))
            trips  = item["total_trips"]
            result.append({
                **item,
                "variance_kg": float(rounded(actual - agreed)),
                "collection_efficiency_percent": float(percent(actual, agreed)),
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(trips)) if trips else ZERO
                ),
            })
        return result

    def _build_panchayat_comparison(self, rows):
        # Sum actual across all waste types and months; count agreed once per (month, panchayat).
        panchayats = {}
        seen_agreed = set()
        for row in rows:
            pid = row["panchayat_id"]
            if pid not in panchayats:
                panchayats[pid] = {
                    "panchayat_id": pid,
                    "panchayat_name": row["panchayat_name"],
                    "total_agreed_weight": ZERO,
                    "total_actual_weight": ZERO,
                }
            panchayats[pid]["total_actual_weight"] += decimal_value(row["total_actual_weight"])

            key = (row["month"], pid)
            if key not in seen_agreed:
                seen_agreed.add(key)
                panchayats[pid]["total_agreed_weight"] += decimal_value(row["total_agreed_weight"])

        result = []
        for item in panchayats.values():
            agreed = item["total_agreed_weight"]
            actual = item["total_actual_weight"]
            variance = actual - agreed
            result.append({
                "panchayat_id": item["panchayat_id"],
                "panchayat_name": item["panchayat_name"],
                "total_agreed_weight": float(rounded(agreed)),
                "total_actual_weight": float(rounded(actual)),
                "variance_kg": float(rounded(variance)),
                "collection_efficiency_percent": float(percent(actual, agreed)),
                "report_status": performance_status(actual, agreed),
            })
        return sorted(result, key=lambda r: abs(r["variance_kg"]), reverse=True)

    def _build_totals(self, rows):
        # Sum actual across all rows; count agreed once per (month, panchayat) pair.
        seen_agreed = set()
        total_agreed = ZERO
        total_actual = ZERO
        total_trips  = 0
        total_points = 0

        for r in rows:
            total_actual += decimal_value(r["total_actual_weight"])
            total_trips  += r["total_trips"]
            total_points += r["collection_points_covered"]

            key = (r["month"], r["panchayat_id"])
            if key not in seen_agreed:
                seen_agreed.add(key)
                total_agreed += decimal_value(r["total_agreed_weight"])

        return {
            "total_agreed_weight":           float(rounded(total_agreed)),
            "total_actual_weight":           float(rounded(total_actual)),
            "variance_kg":                   float(rounded(total_actual - total_agreed)),
            "collection_efficiency_percent": float(percent(total_actual, total_agreed)),
            "average_weight_per_trip":       float(
                rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
            ),
            "coverage_efficiency_percent":   float(percent(total_points, total_trips)),
            "total_trips":                   total_trips,
            "collection_points_covered":     total_points,
            "report_status":                 performance_status(total_actual, total_agreed),
        }
