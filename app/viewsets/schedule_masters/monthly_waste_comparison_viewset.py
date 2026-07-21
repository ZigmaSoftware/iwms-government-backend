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
from app.utils.waste_type_breakdown import bulk_waste_type_rows_for_trip_assignments


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
            "corporation", "municipality", "town_panchayat", "panchayat_union", "panchayat",
        ).prefetch_related("waste_types").filter(
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
            base_qs = base_qs.filter(waste_types=waste_type_param)

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

        # ── Aggregate by (year, month, local body) — trip-log level, so a
        # trip is never double counted here even if it spans waste types ──
        annotation_kwargs = {
            "total_trips": Count("unique_id", distinct=True),
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

        location_qs = base_qs.values(
            "trip_date__year", "trip_date__month", *group_fields, *name_fields,
        ).annotate(**annotation_kwargs)

        # ── per-waste-type weight, computed separately (a trip can now
        # legitimately appear under more than one waste type) ─────────────
        trip_assignment_ids = list(
            base_qs.values_list("trip_assignment_id_id", flat=True).distinct()
        )
        wt_rows = bulk_waste_type_rows_for_trip_assignments(
            trip_assignment_ids, source=source, extra_group_by=("trip_date",),
        )
        if waste_type_param:
            wt_rows = [r for r in wt_rows if r["waste_type_id"] == waste_type_param]

        trip_log_info = base_qs.values(
            "trip_assignment_id_id", "trip_date", *group_fields,
        )
        info_by_assignment = {}
        for r in trip_log_info:
            info_by_assignment.setdefault(r["trip_assignment_id_id"], []).append(r)

        bucket_totals = {}  # (year, month, local_body_field, local_body_id, waste_type_id) -> accumulator
        for wt_row in wt_rows:
            infos = info_by_assignment.get(wt_row["trip_assignment_id"], [])
            for info in infos:
                if str(info["trip_date"]) != str(wt_row["trip_date"]):
                    continue
                local_body_field, local_body_id = self._local_body_from_row(info)
                if not local_body_id:
                    continue
                year_val, month_val = info["trip_date"].year, info["trip_date"].month
                key = (year_val, month_val, local_body_field, local_body_id, wt_row["waste_type_id"])
                bucket = bucket_totals.setdefault(key, {
                    "year": year_val,
                    "month": month_val,
                    "local_body_field": local_body_field,
                    "local_body_id": local_body_id,
                    "waste_type_id": wt_row["waste_type_id"],
                    "waste_type_name": wt_row["waste_type_name"],
                    "weight_kg": ZERO,
                    "trip_assignment_ids": set(),
                })
                bucket["weight_kg"] += wt_row["weight_kg"]
                bucket["trip_assignment_ids"].add(wt_row["trip_assignment_id"])

        local_body_names = {}
        for r in location_qs:
            lb_field, lb_id = self._local_body_from_row(r)
            if lb_id:
                local_body_names[(lb_field, lb_id)] = r.get(LOCAL_BODY_NAME_FIELDS[lb_field]) or lb_id

        rows = []
        for (year_val, month_val, local_body_field, local_body_id, waste_type_id), bucket in bucket_totals.items():
            actual = bucket["weight_kg"]
            total_trips = len(bucket["trip_assignment_ids"])
            local_body_name = local_body_names.get((local_body_field, local_body_id), local_body_id)
            month_str = f"{year_val}-{month_val:02d}"

            unique_id = f"MWR-{month_str}-{local_body_id}-{waste_type_id}"

            rows.append({
                "unique_id": unique_id,
                "month": month_str,
                "local_body_field": local_body_field,
                "local_body_type": LOCAL_BODY_LABELS.get(local_body_field, local_body_field),
                "local_body_id": local_body_id,
                "local_body_name": local_body_name,
                "waste_type_id": waste_type_id,
                "waste_type": bucket["waste_type_name"],
                "total_actual_weight": float(rounded(actual)),
                "total_trips": total_trips,
                # not meaningfully splittable per waste type from the
                # underlying collection records — reported at the
                # local-body/month bucket level instead (see location_rows).
                "collection_points_covered": 0,
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(total_trips)) if total_trips else ZERO
                ),
            })

        sort_mode = request.query_params.get("sort", "weight").lower()
        if sort_mode == "trips":
            rows.sort(key=lambda r: r["total_trips"], reverse=True)
        else:
            rows.sort(key=lambda r: r["total_actual_weight"], reverse=True)

        location_rows = self._build_location_rows(location_qs)

        return Response({
            "source": source,
            "results": rows,
            "monthly_trends": self._build_monthly_trends(location_rows),
            "location_comparison": self._build_location_comparison(location_rows),
            "waste_type_breakdown": self._build_waste_type_breakdown(rows),
            "kpis": self._build_totals(location_rows, rows),
        })

    def _build_location_rows(self, location_qs):
        """Trip-log-level rows (month, local body) — one row per group,
        independent of waste type, used for totals/trends/location comparison
        so a multi-waste-type trip is never double counted there."""
        rows = []
        for row in location_qs:
            local_body_field, local_body_id = self._local_body_from_row(row)
            if not local_body_id:
                continue
            local_body_name = row.get(LOCAL_BODY_NAME_FIELDS[local_body_field]) or local_body_id
            year_val = row["trip_date__year"]
            month_val = row["trip_date__month"]
            actual = decimal_value(row["total_actual_weight"])
            total_trips = int(row["total_trips"] or 0)
            points = int(row["collection_points_covered"] or 0)
            rows.append({
                "month": f"{year_val}-{month_val:02d}",
                "local_body_field": local_body_field,
                "local_body_type": LOCAL_BODY_LABELS.get(local_body_field, local_body_field),
                "local_body_id": local_body_id,
                "local_body_name": local_body_name,
                "total_actual_weight": float(rounded(actual)),
                "total_trips": total_trips,
                "collection_points_covered": points,
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(total_trips)) if total_trips else ZERO
                ),
            })
        return rows

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

    def _build_totals(self, location_rows, waste_type_rows):
        """Overall KPI totals."""
        total_actual = ZERO
        total_trips  = 0
        total_points = 0

        for r in location_rows:
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
            "waste_type_count":          len({r["waste_type_id"] for r in waste_type_rows}),
            "local_body_count":          len({r["local_body_id"] for r in location_rows}),
        }
