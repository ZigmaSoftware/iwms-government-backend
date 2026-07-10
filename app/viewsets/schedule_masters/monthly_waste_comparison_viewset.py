"""
Monthly Waste Collection Report — computed live from DailyTripLog.

Pure collection reporting (no agreed/target comparison):
  actual_weight      = Sum(collected_weight_kg) per (month, local body, waste_type)

Response:
  results               per (month, local body, waste type) row, including
                        local_body_type/local_body_name for display
  monthly_trends         totals per month
  location_comparison    totals per local body (across all waste types)
  waste_type_breakdown   totals per waste type (for composition charts)
  kpis                    overall totals

Query params:
  source  bin (default) | household | all
  month   YYYY-MM
  waste_type_id, and any of corporation_id | municipality_id | town_panchayat_id |
  panchayat_union_id | panchayat_id — optional filters
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Sum, F, ExpressionWrapper, DecimalField, Value
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.monthly_weight_report import MonthlyWeightReport
from app.serializers.schedule_masters.monthly_weight_report_serializer import MonthlyWeightReportSerializer


ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")

LOCAL_BODY_FIELDS = (
    "corporation",
    "municipality",
    "town_panchayat",
    "panchayat_union",
    "panchayat",
)

LOCAL_BODY_LABELS = {
    "corporation": "Corporation",
    "municipality": "Municipality",
    "town_panchayat": "Town Panchayat",
    "panchayat_union": "Panchayat Union",
    "panchayat": "Panchayat",
}

LOCAL_BODY_NAME_FIELDS = {
    "corporation": "corporation__corporation_name",
    "municipality": "municipality__municipality_name",
    "town_panchayat": "town_panchayat__town_panchayat_name",
    "panchayat_union": "panchayat_union__union_name",
    "panchayat": "panchayat__panchayat_name",
}


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


class MonthlyWasteComparisonReportViewSet(viewsets.ModelViewSet):
    permission_resource = "MonthlyWasteComparisonReport"
    queryset = MonthlyWeightReport.objects.select_related(
        "corporation", "municipality", "town_panchayat", "panchayat_union", "panchayat", "waste_type_id"
    )
    serializer_class = MonthlyWeightReportSerializer
    lookup_field = "unique_id"

    def list(self, request):
        # ── base queryset: only confirmed trip logs ──────────────────────
        base_qs = DailyTripLog.objects.select_related(
            "corporation", "municipality", "town_panchayat", "panchayat_union", "panchayat", "waste_type_id",
        ).filter(
            is_deleted=False,
            log_status__in=[
                DailyTripLog.LOG_STATUS_SUBMITTED,
                DailyTripLog.LOG_STATUS_VERIFIED,
            ],
        )

        base_qs = self.filter_queryset(base_qs)

        # ── month / local body / waste_type filters ──────────────────────
        month_param = request.query_params.get("month")
        waste_type_param = request.query_params.get("waste_type_id")

        if month_param:
            try:
                year, mon = month_param.split("-")
                base_qs = base_qs.filter(
                    trip_date__year=int(year),
                    trip_date__month=int(mon),
                )
            except (ValueError, AttributeError):
                pass

        for field in LOCAL_BODY_FIELDS:
            value = request.query_params.get(f"{field}_id")
            if value:
                base_qs = base_qs.filter(**{f"{field}_id": value})

        if waste_type_param:
            base_qs = base_qs.filter(waste_type_id=waste_type_param)

        # ── choose weight source ─────────────────────────────────────────
        source = request.query_params.get("source", "bin").lower()
        if source == "household":
            weight_field = "household_collected_weight_kg"
        elif source == "all":
            weight_field = None
        else:
            weight_field = "collected_weight_kg"

        group_fields = [f"{field}_id" for field in LOCAL_BODY_FIELDS]
        name_fields = list(LOCAL_BODY_NAME_FIELDS.values())

        # ── Aggregate by (year, month, local body, waste_type) ───────────
        annotation_kwargs = {
            "total_trips": Count("unique_id"),
            "collection_points_covered": Count("collection_point_id", distinct=True),
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

        grouped_qs = base_qs.values(
            "trip_date__year",
            "trip_date__month",
            *group_fields,
            *name_fields,
            "waste_type_id",
            "waste_type_id__waste_type_name",
        ).annotate(**annotation_kwargs)

        rows = []
        for row in grouped_qs:
            local_body_field, local_body_id = self._local_body_from_row(row)
            if not local_body_id:
                continue
            local_body_name = row.get(LOCAL_BODY_NAME_FIELDS[local_body_field]) or local_body_id

            year_val  = row["trip_date__year"]
            month_val = row["trip_date__month"]
            month_str = f"{year_val}-{month_val:02d}"

            actual      = decimal_value(row["total_actual_weight"])
            total_trips = int(row["total_trips"] or 0)
            points      = int(row["collection_points_covered"] or 0)

            unique_id = f"MWR-{month_str}-{local_body_id}-{row['waste_type_id']}"

            rows.append({
                "unique_id": unique_id,
                "month": month_str,
                "local_body_field": local_body_field,
                "local_body_type": LOCAL_BODY_LABELS.get(local_body_field, local_body_field),
                "local_body_id": local_body_id,
                "local_body_name": local_body_name,
                "waste_type_id": row["waste_type_id"],
                "waste_type": (
                    row["waste_type_id__waste_type_name"] or row["waste_type_id"]
                ),
                "total_actual_weight": float(rounded(actual)),
                "total_trips": total_trips,
                "collection_points_covered": points,
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(total_trips)) if total_trips else ZERO
                ),
            })

        sort_mode = request.query_params.get("sort", "weight").lower()
        if sort_mode == "trips":
            rows.sort(key=lambda r: r["total_trips"], reverse=True)
        else:
            rows.sort(key=lambda r: r["total_actual_weight"], reverse=True)

        return Response({
            "source": source,
            "results": rows,
            "monthly_trends": self._build_monthly_trends(rows),
            "location_comparison": self._build_location_comparison(rows),
            "waste_type_breakdown": self._build_waste_type_breakdown(rows),
            "kpis": self._build_totals(rows),
        })

    # ── local body resolution ────────────────────────────────────────────

    def _local_body_from_row(self, row):
        """Most specific populated local-body field for a grouped row."""
        for field in LOCAL_BODY_FIELDS:
            value = row.get(f"{field}_id")
            if value:
                return field, value
        return None, None

    # ── analytics helpers ────────────────────────────────────────────────

    def _build_monthly_trends(self, rows):
        """Aggregate by month."""
        trends: dict = {}
        for row in rows:
            m = row["month"]
            trends.setdefault(m, {
                "month": m,
                "total_actual_weight": 0.0,
                "total_trips": 0,
                "collection_points_covered": 0,
            })
            trends[m]["total_actual_weight"]       += row["total_actual_weight"]
            trends[m]["total_trips"]               += row["total_trips"]
            trends[m]["collection_points_covered"] += row["collection_points_covered"]

        result = []
        for item in sorted(trends.values(), key=lambda x: str(x["month"])):
            actual = Decimal(str(item["total_actual_weight"]))
            trips  = item["total_trips"]
            result.append({
                **item,
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(trips)) if trips else ZERO
                ),
            })
        return result

    def _build_location_comparison(self, rows):
        """Aggregate by local body."""
        locations: dict = {}
        for row in rows:
            lid = row["local_body_id"]
            if lid not in locations:
                locations[lid] = {
                    "local_body_field": row["local_body_field"],
                    "local_body_type": row["local_body_type"],
                    "local_body_id": lid,
                    "local_body_name": row["local_body_name"],
                    "total_actual_weight": ZERO,
                    "total_trips": 0,
                    "collection_points_covered": 0,
                }
            locations[lid]["total_actual_weight"] += decimal_value(row["total_actual_weight"])
            locations[lid]["total_trips"] += row["total_trips"]
            locations[lid]["collection_points_covered"] += row["collection_points_covered"]

        result = []
        for item in locations.values():
            actual = item["total_actual_weight"]
            trips = item["total_trips"]
            result.append({
                "local_body_field": item["local_body_field"],
                "local_body_type": item["local_body_type"],
                "local_body_id": item["local_body_id"],
                "local_body_name": item["local_body_name"],
                "total_actual_weight": float(rounded(actual)),
                "total_trips": trips,
                "collection_points_covered": item["collection_points_covered"],
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(trips)) if trips else ZERO
                ),
            })
        return sorted(result, key=lambda r: r["total_actual_weight"], reverse=True)

    def _build_waste_type_breakdown(self, rows):
        """Aggregate by waste type — for the waste composition pie chart."""
        types: dict = {}
        for row in rows:
            key = row["waste_type_id"]
            if key not in types:
                types[key] = {
                    "waste_type_id": key,
                    "waste_type": row["waste_type"],
                    "total_actual_weight": ZERO,
                    "total_trips": 0,
                    "collection_points_covered": 0,
                }
            types[key]["total_actual_weight"] += decimal_value(row["total_actual_weight"])
            types[key]["total_trips"] += row["total_trips"]
            types[key]["collection_points_covered"] += row["collection_points_covered"]

        total_actual = sum((t["total_actual_weight"] for t in types.values()), ZERO)

        result = []
        for item in types.values():
            actual = item["total_actual_weight"]
            result.append({
                "waste_type_id": item["waste_type_id"],
                "waste_type": item["waste_type"],
                "total_actual_weight": float(rounded(actual)),
                "total_trips": item["total_trips"],
                "collection_points_covered": item["collection_points_covered"],
                "share_percent": float(percent(actual, total_actual)),
            })
        return sorted(result, key=lambda r: r["total_actual_weight"], reverse=True)

    def _build_totals(self, rows):
        """Overall KPI totals."""
        total_actual = ZERO
        total_trips  = 0
        total_points = 0

        for r in rows:
            total_actual += decimal_value(r["total_actual_weight"])
            total_trips  += r["total_trips"]
            total_points += r["collection_points_covered"]

        return {
            "total_actual_weight":       float(rounded(total_actual)),
            "average_weight_per_trip":   float(
                rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
            ),
            "total_trips":               total_trips,
            "collection_points_covered": total_points,
            "waste_type_count":          len({r["waste_type_id"] for r in rows}),
            "local_body_count":          len({r["local_body_id"] for r in rows}),
        }
