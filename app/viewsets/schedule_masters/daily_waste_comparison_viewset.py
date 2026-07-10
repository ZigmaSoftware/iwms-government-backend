"""
Daily Waste Comparison — computed live from DailyTripLog.

Data source: DailyTripLog (Submitted + Verified logs only)
  actual_weight_kg  = Sum(collected_weight_kg) per (date, local body, waste_type)
                      OR household_collected_weight_kg when source=household
                      OR both combined when source=all
  agreed_weight_kg  = Panchayat.agreed_weight_kg when the local body is a Panchayat,
                      else 0 (no per-location daily target source exists for the
                      other local body types yet)
  total_trips       = Count of trip logs in the group
  points_covered    = Count of distinct collection_point_id in the group

Query params:
  source  bin (default) | household | all
  Any of: corporation_id | municipality_id | town_panchayat_id |
          panchayat_union_id | panchayat_id — optional local body filter
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Sum, F, ExpressionWrapper, DecimalField, Value
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.serializers.schedule_masters.daily_waste_comparison_serializer import DailyWasteComparisonSerializer
from app.models.schedule_masters.daily_waste_comparison import DailyWasteComparison

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")

LOCAL_BODY_FIELDS = (
    "corporation",
    "municipality",
    "town_panchayat",
    "panchayat_union",
    "panchayat",
)


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


class DailyWasteComparisonViewSet(viewsets.ModelViewSet):
    permission_resource = "DailyWasteComparison"
    # Keep original queryset for retrieve/update/delete operations on the static table
    queryset = DailyWasteComparison.objects.select_related(
        "corporation", "municipality", "town_panchayat", "panchayat_union", "panchayat", "waste_type_id"
    )
    serializer_class = DailyWasteComparisonSerializer
    lookup_field = "unique_id"

    def list(self, request):
        # ── base queryset: only confirmed trip logs ──────────────────────
        queryset = DailyTripLog.objects.select_related(
            "corporation", "municipality", "town_panchayat", "panchayat_union", "panchayat", "waste_type_id",
        ).filter(
            is_deleted=False,
            log_status__in=[
                DailyTripLog.LOG_STATUS_SUBMITTED,
                DailyTripLog.LOG_STATUS_VERIFIED,
            ],
        )

        queryset = self.filter_queryset(queryset)

        # ── date / month / local body / waste_type filters ───────────────
        date_param = request.query_params.get("date")
        month_param = request.query_params.get("month")
        waste_type_param = request.query_params.get("waste_type_id")

        if date_param:
            queryset = queryset.filter(trip_date=date_param)
        elif month_param:
            try:
                year, mon = month_param.split("-")
                queryset = queryset.filter(
                    trip_date__year=int(year),
                    trip_date__month=int(mon),
                )
            except (ValueError, AttributeError):
                pass

        for field in LOCAL_BODY_FIELDS:
            value = request.query_params.get(f"{field}_id")
            if value:
                queryset = queryset.filter(**{f"{field}_id": value})

        if waste_type_param:
            queryset = queryset.filter(waste_type_id=waste_type_param)

        # ── choose weight source ─────────────────────────────────────────
        source = request.query_params.get("source", "bin").lower()
        if source == "household":
            weight_field = "household_collected_weight_kg"
        elif source == "all":
            weight_field = None  # handled below with combined expression
        else:
            weight_field = "collected_weight_kg"

        # ── aggregate by (trip_date, local body, waste_type) ──────────────
        annotation_kwargs = {
            "total_trips": Count("unique_id"),
            "collection_points_covered": Count("collection_point_id", distinct=True),
        }
        if weight_field:
            annotation_kwargs["total_actual_weight"] = Sum(weight_field)
        else:
            # source=all: sum both bin and household weight
            annotation_kwargs["total_actual_weight"] = Sum(
                ExpressionWrapper(
                    Coalesce(F("collected_weight_kg"), Value(0, output_field=DecimalField()))
                    + Coalesce(F("household_collected_weight_kg"), Value(0, output_field=DecimalField())),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )

        group_fields = [f"{field}_id" for field in LOCAL_BODY_FIELDS]
        grouped_qs = queryset.values(
            "trip_date",
            *group_fields,
            "panchayat__agreed_weight_kg",
            "waste_type_id",
            "waste_type_id__waste_type_name",
        ).annotate(**annotation_kwargs)

        rows = []
        for row in grouped_qs:
            local_body_field, local_body_id = self._local_body_from_row(row)
            if not local_body_id:
                continue
            agreed = decimal_value(
                row.get("panchayat__agreed_weight_kg") if local_body_field == "panchayat" else 0
            )
            actual = decimal_value(row["total_actual_weight"])
            variance = actual - agreed
            total_trips = int(row["total_trips"] or 0)
            points = int(row["collection_points_covered"] or 0)

            unique_id = (
                f"DWC-{row['trip_date']}-{local_body_id}-{row['waste_type_id']}"
            )

            rows.append({
                "unique_id": unique_id,
                "collection_date": str(row["trip_date"]),
                "local_body_field": local_body_field,
                "local_body_id": local_body_id,
                "waste_type_id": row["waste_type_id"],
                "waste_type": (
                    row["waste_type_id__waste_type_name"] or row["waste_type_id"]
                ),
                "agreed_weight_kg": float(rounded(agreed)),
                "actual_weight_kg": float(rounded(actual)),
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
            "date_trends": self._build_date_trends(rows),
            "location_comparison": self._build_location_comparison(rows),
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

    def _build_date_trends(self, rows):
        trends = {}
        for row in rows:
            date = row["collection_date"]
            trends.setdefault(date, {
                "collection_date": date,
                "agreed_weight_kg": 0.0, "actual_weight_kg": 0.0,
                "total_trips": 0, "collection_points_covered": 0,
            })
            trends[date]["actual_weight_kg"]          += row["actual_weight_kg"]
            trends[date]["agreed_weight_kg"]          += row["agreed_weight_kg"]
            trends[date]["total_trips"]               += row["total_trips"]
            trends[date]["collection_points_covered"] += row["collection_points_covered"]

        result = []
        for item in sorted(trends.values(), key=lambda x: str(x["collection_date"])):
            agreed = Decimal(str(item["agreed_weight_kg"]))
            actual = Decimal(str(item["actual_weight_kg"]))
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

    def _build_location_comparison(self, rows):
        locations = {}
        for row in rows:
            lid = row["local_body_id"]
            if lid not in locations:
                locations[lid] = {
                    "local_body_field": row["local_body_field"],
                    "local_body_id": lid,
                    "agreed_weight_kg": ZERO,
                    "actual_weight_kg": ZERO,
                }
            locations[lid]["actual_weight_kg"] += decimal_value(row["actual_weight_kg"])
            locations[lid]["agreed_weight_kg"] += decimal_value(row["agreed_weight_kg"])

        result = []
        for item in locations.values():
            agreed = item["agreed_weight_kg"]
            actual = item["actual_weight_kg"]
            variance = actual - agreed
            result.append({
                "local_body_field": item["local_body_field"],
                "local_body_id": item["local_body_id"],
                "agreed_weight_kg": float(rounded(agreed)),
                "actual_weight_kg": float(rounded(actual)),
                "variance_kg": float(rounded(variance)),
                "collection_efficiency_percent": float(percent(actual, agreed)),
                "report_status": performance_status(actual, agreed),
            })
        return sorted(result, key=lambda r: abs(r["variance_kg"]), reverse=True)

    def _build_totals(self, rows):
        total_agreed = ZERO
        total_actual = ZERO
        total_trips  = 0
        total_points = 0

        for r in rows:
            total_actual += decimal_value(r["actual_weight_kg"])
            total_agreed += decimal_value(r["agreed_weight_kg"])
            total_trips  += r["total_trips"]
            total_points += r["collection_points_covered"]

        return {
            "total_agreed_weight_kg":          float(rounded(total_agreed)),
            "total_actual_weight_kg":          float(rounded(total_actual)),
            "variance_kg":                     float(rounded(total_actual - total_agreed)),
            "collection_efficiency_percent":   float(percent(total_actual, total_agreed)),
            "average_weight_per_trip":         float(
                rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
            ),
            "coverage_efficiency_percent":     float(percent(total_points, total_trips)),
            "total_trips":                     total_trips,
            "collection_points_covered":       total_points,
            "report_status":                   performance_status(total_actual, total_agreed),
        }
