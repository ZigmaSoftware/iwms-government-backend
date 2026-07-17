"""
State Leader — Monthly & Daily Waste Comparison
Authenticated-only endpoints — no module permission check (see AUTH_ONLY_SUFFIXES).

Mirrors the aggregation pattern of MonthlyWasteComparisonReportViewSet /
DailyWasteComparisonViewSet (app/viewsets/schedule_masters/), but:
  - scoped server-side to the authenticated StateLeaderLogin's own state
    (never a client-supplied param — DailyTripLog already carries a direct,
    auto-populated `state_id` column, see DailyTripLog.copy_flat_geo()), and
  - grouped by District within the state instead of arbitrary local-body
    type, since a state-wide comparison is most meaningful per-district.

Query params (both endpoints):
  source  bin (default) | household | all
  sort    weight (default) | trips

Monthly-only:
  month   YYYY-MM — optional; omitted returns every month on record (a true
          month-over-month comparison).

Daily-only:
  month   YYYY-MM — defaults to the current month (avoids an unbounded
          full-history scan).
  date    YYYY-MM-DD — optional, narrows to a single day.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.state_leader_login import StateLeaderLogin
from app.models.schedule_masters.daily_trip_log import DailyTripLog

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


def weight_annotation(source):
    """Return the Sum() annotation expression for the chosen weight source."""
    if source == "household":
        return Sum("household_collected_weight_kg")
    if source == "all":
        return Sum(
            ExpressionWrapper(
                Coalesce(F("collected_weight_kg"), Value(0, output_field=DecimalField()))
                + Coalesce(F("household_collected_weight_kg"), Value(0, output_field=DecimalField())),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
    return Sum("collected_weight_kg")


class _StateWasteComparisonBase(ViewSet):
    permission_classes = [IsAuthenticated]

    def _get_state(self, request):
        user = request.user
        if isinstance(user, StateLeaderLogin):
            return getattr(user, "state_id", None)
        return None

    def _base_queryset(self, state_uid):
        return DailyTripLog.objects.select_related(
            "district", "waste_type_id"
        ).filter(
            is_deleted=False,
            state_id=state_uid,
            log_status__in=[
                DailyTripLog.LOG_STATUS_SUBMITTED,
                DailyTripLog.LOG_STATUS_VERIFIED,
            ],
        )

    def _district_comparison(self, rows, weight_key):
        districts = {}
        for row in rows:
            did = row["district_id"]
            if did not in districts:
                districts[did] = {
                    "district_id": did,
                    "district_name": row["district_name"],
                    "total_actual_weight": ZERO,
                    "total_trips": 0,
                    "collection_points_covered": 0,
                }
            districts[did]["total_actual_weight"] += decimal_value(row[weight_key])
            districts[did]["total_trips"] += row["total_trips"]
            districts[did]["collection_points_covered"] += row["collection_points_covered"]

        result = []
        for item in districts.values():
            actual = item["total_actual_weight"]
            trips = item["total_trips"]
            result.append({
                "district_id": item["district_id"],
                "district_name": item["district_name"],
                "total_actual_weight": float(rounded(actual)),
                "total_trips": trips,
                "collection_points_covered": item["collection_points_covered"],
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(trips)) if trips else ZERO
                ),
            })
        return sorted(result, key=lambda r: r["total_actual_weight"], reverse=True)

    def _waste_type_breakdown(self, rows, weight_key):
        types = {}
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
            types[key]["total_actual_weight"] += decimal_value(row[weight_key])
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

    def _totals(self, rows, weight_key):
        total_actual = ZERO
        total_trips = 0
        total_points = 0
        for r in rows:
            total_actual += decimal_value(r[weight_key])
            total_trips += r["total_trips"]
            total_points += r["collection_points_covered"]

        return {
            "total_actual_weight": float(rounded(total_actual)),
            "average_weight_per_trip": float(
                rounded(total_actual / Decimal(total_trips)) if total_trips else ZERO
            ),
            "total_trips": total_trips,
            "collection_points_covered": total_points,
            "waste_type_count": len({r["waste_type_id"] for r in rows}),
            "district_count": len({r["district_id"] for r in rows}),
        }


class StateMonthlyWasteComparisonViewSet(_StateWasteComparisonBase):
    def list(self, request):
        state = self._get_state(request)
        if not state:
            return Response({"detail": "State not found for this leader."}, status=403)
        state_uid = state.unique_id

        qs = self._base_queryset(state_uid)

        month_param = request.query_params.get("month")
        if month_param:
            try:
                year, mon = month_param.split("-")
                qs = qs.filter(trip_date__year=int(year), trip_date__month=int(mon))
            except (ValueError, AttributeError):
                pass

        source = request.query_params.get("source", "bin").lower()

        grouped_qs = qs.values(
            "trip_date__year",
            "trip_date__month",
            "district_id",
            "district__name",
            "waste_type_id",
            "waste_type_id__waste_type_name",
        ).annotate(
            total_actual_weight=weight_annotation(source),
            total_trips=Count("unique_id"),
            collection_points_covered=Count("collection_point_id", distinct=True),
        )

        rows = []
        for row in grouped_qs:
            if not row["district_id"]:
                continue
            year_val = row["trip_date__year"]
            month_val = row["trip_date__month"]
            actual = decimal_value(row["total_actual_weight"])
            total_trips = int(row["total_trips"] or 0)
            points = int(row["collection_points_covered"] or 0)
            rows.append({
                "unique_id": f"SMWC-{year_val}-{month_val:02d}-{row['district_id']}-{row['waste_type_id']}",
                "month": f"{year_val}-{month_val:02d}",
                "district_id": row["district_id"],
                "district_name": row["district__name"] or row["district_id"],
                "waste_type_id": row["waste_type_id"],
                "waste_type": row["waste_type_id__waste_type_name"] or row["waste_type_id"],
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

        monthly_trends = {}
        for row in rows:
            m = row["month"]
            monthly_trends.setdefault(m, {
                "month": m, "total_actual_weight": 0.0, "total_trips": 0, "collection_points_covered": 0,
            })
            monthly_trends[m]["total_actual_weight"] += row["total_actual_weight"]
            monthly_trends[m]["total_trips"] += row["total_trips"]
            monthly_trends[m]["collection_points_covered"] += row["collection_points_covered"]

        trends_list = []
        for item in sorted(monthly_trends.values(), key=lambda x: str(x["month"])):
            actual = Decimal(str(item["total_actual_weight"]))
            trips = item["total_trips"]
            trends_list.append({
                **item,
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(trips)) if trips else ZERO
                ),
            })

        return Response({
            "state_id": state_uid,
            "state_name": getattr(state, "name", "") or "",
            "source": source,
            "results": rows,
            "monthly_trends": trends_list,
            "district_comparison": self._district_comparison(rows, "total_actual_weight"),
            "waste_type_breakdown": self._waste_type_breakdown(rows, "total_actual_weight"),
            "kpis": self._totals(rows, "total_actual_weight"),
        })


class StateDailyWasteComparisonViewSet(_StateWasteComparisonBase):
    def list(self, request):
        state = self._get_state(request)
        if not state:
            return Response({"detail": "State not found for this leader."}, status=403)
        state_uid = state.unique_id

        qs = self._base_queryset(state_uid)

        date_param = request.query_params.get("date")
        month_param = request.query_params.get("month")
        if date_param:
            qs = qs.filter(trip_date=date_param)
        else:
            if not month_param:
                today = timezone.localdate()
                month_param = f"{today.year}-{today.month:02d}"
            try:
                year, mon = month_param.split("-")
                qs = qs.filter(trip_date__year=int(year), trip_date__month=int(mon))
            except (ValueError, AttributeError):
                pass

        source = request.query_params.get("source", "bin").lower()

        grouped_qs = qs.values(
            "trip_date",
            "district_id",
            "district__name",
            "waste_type_id",
            "waste_type_id__waste_type_name",
        ).annotate(
            total_actual_weight=weight_annotation(source),
            total_trips=Count("unique_id"),
            collection_points_covered=Count("collection_point_id", distinct=True),
        )

        rows = []
        for row in grouped_qs:
            if not row["district_id"]:
                continue
            actual = decimal_value(row["total_actual_weight"])
            total_trips = int(row["total_trips"] or 0)
            points = int(row["collection_points_covered"] or 0)
            rows.append({
                "unique_id": f"SDWC-{row['trip_date']}-{row['district_id']}-{row['waste_type_id']}",
                "collection_date": str(row["trip_date"]),
                "district_id": row["district_id"],
                "district_name": row["district__name"] or row["district_id"],
                "waste_type_id": row["waste_type_id"],
                "waste_type": row["waste_type_id__waste_type_name"] or row["waste_type_id"],
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

        date_trends = {}
        for row in rows:
            d = row["collection_date"]
            date_trends.setdefault(d, {
                "collection_date": d, "actual_weight_kg": 0.0, "total_trips": 0, "collection_points_covered": 0,
            })
            date_trends[d]["actual_weight_kg"] += row["actual_weight_kg"]
            date_trends[d]["total_trips"] += row["total_trips"]
            date_trends[d]["collection_points_covered"] += row["collection_points_covered"]

        trends_list = []
        for item in sorted(date_trends.values(), key=lambda x: str(x["collection_date"])):
            actual = Decimal(str(item["actual_weight_kg"]))
            trips = item["total_trips"]
            trends_list.append({
                **item,
                "average_weight_per_trip": float(
                    rounded(actual / Decimal(trips)) if trips else ZERO
                ),
            })

        return Response({
            "state_id": state_uid,
            "state_name": getattr(state, "name", "") or "",
            "source": source,
            "results": rows[:300],
            "date_trends": trends_list,
            "district_comparison": self._district_comparison(rows, "actual_weight_kg"),
            "waste_type_breakdown": self._waste_type_breakdown(rows, "actual_weight_kg"),
            "kpis": self._totals(rows, "actual_weight_kg"),
        })
