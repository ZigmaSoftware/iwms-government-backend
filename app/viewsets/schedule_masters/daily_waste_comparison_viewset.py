"""
Daily Waste Collection Report — computed live from DailyTripLog.

Pure collection reporting (no agreed/target comparison):
  actual_weight_kg  = Sum(collected_weight_kg) per (date, local body, waste_type)
                      OR household_collected_weight_kg when source=household
                      OR both combined when source=all
  total_trips       = Count of trip logs in the group
  points_covered    = Count of distinct collection_point_id in the group

Response:
  results               per (date, local body, waste type) row, including
                        local_body_type/local_body_name for display
  date_trends           totals per date
  location_comparison   totals per local body (across all waste types)
  waste_type_breakdown  totals per waste type (for composition charts)
  kpis                  overall totals

Query params:
  source  bin (default) | household | all
  date, month  optional date filters
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
        name_fields = list(LOCAL_BODY_NAME_FIELDS.values())
        grouped_qs = queryset.values(
            "trip_date",
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
            actual = decimal_value(row["total_actual_weight"])
            total_trips = int(row["total_trips"] or 0)
            points = int(row["collection_points_covered"] or 0)

            unique_id = (
                f"DWC-{row['trip_date']}-{local_body_id}-{row['waste_type_id']}"
            )

            rows.append({
                "unique_id": unique_id,
                "collection_date": str(row["trip_date"]),
                "local_body_field": local_body_field,
                "local_body_type": LOCAL_BODY_LABELS.get(local_body_field, local_body_field),
                "local_body_id": local_body_id,
                "local_body_name": local_body_name,
                "waste_type_id": row["waste_type_id"],
                "waste_type": (
                    row["waste_type_id__waste_type_name"] or row["waste_type_id"]
                ),
                "actual_weight_kg": float(rounded(actual)),
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
            rows.sort(key=lambda r: r["actual_weight_kg"], reverse=True)

        return Response({
            "source": source,
            "results": rows,
            "date_trends": self._build_date_trends(rows),
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

    def _build_date_trends(self, rows):
        trends = {}
        for row in rows:
            date = row["collection_date"]
            trends.setdefault(date, {
                "collection_date": date,
                "actual_weight_kg": 0.0,
                "total_trips": 0,
                "collection_points_covered": 0,
            })
            trends[date]["actual_weight_kg"]          += row["actual_weight_kg"]
            trends[date]["total_trips"]               += row["total_trips"]
            trends[date]["collection_points_covered"] += row["collection_points_covered"]

        result = []
        for item in sorted(trends.values(), key=lambda x: str(x["collection_date"])):
            actual = Decimal(str(item["actual_weight_kg"]))
            trips  = item["total_trips"]
            result.append({
                **item,
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(trips)) if trips else ZERO
                ),
            })
        return result

    def _build_location_comparison(self, rows):
        """Aggregate by local body — the report's per-location totals."""
        locations = {}
        for row in rows:
            lid = row["local_body_id"]
            if lid not in locations:
                locations[lid] = {
                    "local_body_field": row["local_body_field"],
                    "local_body_type": row["local_body_type"],
                    "local_body_id": lid,
                    "local_body_name": row["local_body_name"],
                    "actual_weight_kg": ZERO,
                    "total_trips": 0,
                    "collection_points_covered": 0,
                }
            locations[lid]["actual_weight_kg"] += decimal_value(row["actual_weight_kg"])
            locations[lid]["total_trips"] += row["total_trips"]
            locations[lid]["collection_points_covered"] += row["collection_points_covered"]

        result = []
        for item in locations.values():
            actual = item["actual_weight_kg"]
            trips = item["total_trips"]
            result.append({
                "local_body_field": item["local_body_field"],
                "local_body_type": item["local_body_type"],
                "local_body_id": item["local_body_id"],
                "local_body_name": item["local_body_name"],
                "actual_weight_kg": float(rounded(actual)),
                "total_trips": trips,
                "collection_points_covered": item["collection_points_covered"],
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(trips)) if trips else ZERO
                ),
            })
        return sorted(result, key=lambda r: r["actual_weight_kg"], reverse=True)

    def _build_waste_type_breakdown(self, rows):
        """Aggregate by waste type — for the waste composition pie chart."""
        types: dict = {}
        for row in rows:
            key = row["waste_type_id"]
            if key not in types:
                types[key] = {
                    "waste_type_id": key,
                    "waste_type": row["waste_type"],
                    "actual_weight_kg": ZERO,
                    "total_trips": 0,
                    "collection_points_covered": 0,
                }
            types[key]["actual_weight_kg"] += decimal_value(row["actual_weight_kg"])
            types[key]["total_trips"] += row["total_trips"]
            types[key]["collection_points_covered"] += row["collection_points_covered"]

        total_actual = sum((t["actual_weight_kg"] for t in types.values()), ZERO)

        result = []
        for item in types.values():
            actual = item["actual_weight_kg"]
            result.append({
                "waste_type_id": item["waste_type_id"],
                "waste_type": item["waste_type"],
                "actual_weight_kg": float(rounded(actual)),
                "total_trips": item["total_trips"],
                "collection_points_covered": item["collection_points_covered"],
                "share_percent": float(percent(actual, total_actual)),
            })
        return sorted(result, key=lambda r: r["actual_weight_kg"], reverse=True)

    def _build_totals(self, rows):
        total_actual = ZERO
        total_trips  = 0
        total_points = 0

        for r in rows:
            total_actual += decimal_value(r["actual_weight_kg"])
            total_trips  += r["total_trips"]
            total_points += r["collection_points_covered"]

        return {
            "total_actual_weight_kg":    float(rounded(total_actual)),
            "average_weight_per_trip":   float(
                rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
            ),
            "total_trips":               total_trips,
            "collection_points_covered": total_points,
            "waste_type_count":          len({r["waste_type_id"] for r in rows}),
            "local_body_count":          len({r["local_body_id"] for r in rows}),
        }
