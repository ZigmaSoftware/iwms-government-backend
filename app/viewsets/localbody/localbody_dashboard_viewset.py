"""
Panchayat Leader Dashboard API
Authenticated-only endpoint — no module permission check (see AUTH_ONLY_SUFFIXES).

Data source: DailyTripLog (Submitted + Verified logs only)
  actual_weight   = Sum(collected_weight_kg)
  agreed_weight   = Panchayat.agreed_weight_kg (daily target)
  monthly agreed  = daily_target × COUNT(DISTINCT trip_date) in the month
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin
from app.models.schedule_masters.daily_trip_log import DailyTripLog


ZERO = Decimal("0")
TWO  = Decimal("0.01")


def _r(value):
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


def _pct(num, den):
    d = Decimal(str(den)) if den is not None else ZERO
    if d == ZERO:
        return ZERO
    return _r(Decimal(str(num)) / d * Decimal("100"))


def _var_pct(actual, agreed):
    a = Decimal(str(agreed)) if agreed is not None else ZERO
    if a == ZERO:
        return ZERO
    return _r((Decimal(str(actual)) - a) / a * Decimal("100"))


def _status(actual, agreed):
    a, g = Decimal(str(actual)), Decimal(str(agreed))
    if a > g:
        return "Surplus"
    if a < g:
        return "Deficit"
    return "On Target"


class LocalBodyDashboardViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    # ── helpers ─────────────────────────────────────────────────────────

    def _get_leader(self, request):
        user = request.user
        if isinstance(user, PanchayatLeaderLogin):
            return user
        return None

    def _get_panchayat(self, request):
        leader = self._get_leader(request)
        if leader:
            return getattr(leader, "panchayat_id", None)
        return None

    # ── main endpoint ───────────────────────────────────────────────────

    def list(self, request):
        panchayat = self._get_panchayat(request)
        if not panchayat:
            return Response(
                {"detail": "Panchayat not found for this leader."}, status=403
            )

        panchayat_uid  = panchayat.unique_id
        panchayat_name = getattr(panchayat, "panchayat_name", "") or ""
        month          = request.query_params.get("month", "")
        sort           = request.query_params.get("sort", "absolute").lower()

        # Base queryset: this panchayat, all non-deleted logs
        base_qs = DailyTripLog.objects.filter(
            panchayat_id=panchayat_uid,
            is_deleted=False,
        ).select_related("waste_type_id", "collection_point_id")

        monthly_data = self._monthly_report(base_qs, panchayat, month, sort)
        daily_data   = self._daily_data(base_qs, month)

        return Response({
            "panchayat_name": panchayat_name,

            # ── monthly comparison ──────────────────────────────────────
            "results":              monthly_data["results"],
            "monthly_trends":       monthly_data["monthly_trends"],
            "waste_type_breakdown": monthly_data["waste_type_breakdown"],
            "kpis":                 monthly_data["kpis"],

            # ── daily waste data ─────────────────────────────────────────
            "day_wise_collection":  daily_data["day_wise"],
            "trip_waste_types":     daily_data["waste_types"],
            "day_wise_breakdown":   daily_data["day_wise_breakdown"],
            "daily_rows":           daily_data["daily_rows"],
            "daily_kpis":           daily_data["daily_kpis"],
        })

    # ── monthly report ──────────────────────────────────────────────────

    def _monthly_report(self, base_qs, panchayat, month, sort):
        qs = base_qs
        if month:
            try:
                year, mon = month.split("-")
                qs = qs.filter(
                    trip_date__year=int(year),
                    trip_date__month=int(mon),
                )
            except ValueError:
                pass

        grouped = qs.values(
            "trip_date__year",
            "trip_date__month",
            "waste_type_id",
            "waste_type_id__waste_type_name",
        ).annotate(
            total_actual_weight=Sum("collected_weight_kg"),
            total_trips=Count("unique_id"),
            collection_points=Count("collection_point_id", distinct=True),
            distinct_trip_days=Count("trip_date", distinct=True),
        )

        agreed_per_day = Decimal(str(getattr(panchayat, "agreed_weight_kg", 0) or 0))
        panchayat_uid  = panchayat.unique_id
        panchayat_name = getattr(panchayat, "panchayat_name", "") or ""

        rows = []
        for row in grouped:
            year_val  = row["trip_date__year"]
            month_val = row["trip_date__month"]
            month_str = f"{year_val}-{month_val:02d}"

            trip_days   = int(row["distinct_trip_days"] or 0)
            agreed      = agreed_per_day * Decimal(str(trip_days))
            actual      = Decimal(str(row["total_actual_weight"] or 0))
            var         = actual - agreed
            trips       = int(row["total_trips"] or 0)
            points      = int(row["collection_points"] or 0)

            rows.append({
                "unique_id":                    f"MWR-{month_str}-{panchayat_uid}-{row['waste_type_id']}",
                "month":                        month_str,
                "panchayat_id":                 panchayat_uid,
                "panchayat_name":               panchayat_name,
                "waste_type_id":                row["waste_type_id"],
                "waste_type":                   row["waste_type_id__waste_type_name"] or "—",
                "total_agreed_weight":          float(_r(agreed)),
                "total_actual_weight":          float(_r(actual)),
                "variance_kg":                  float(_r(var)),
                "variance_percent":             float(_var_pct(actual, agreed)),
                "report_status":                _status(actual, agreed),
                "total_trips":                  trips,
                "collection_points_covered":    points,
                "collection_efficiency_percent": float(_pct(actual, agreed)),
                "coverage_efficiency_percent":  float(_pct(points, trips)),
                "average_weight_per_trip":      float(_r(actual / Decimal(trips)) if trips else ZERO),
            })

        if sort == "deficit":
            rows.sort(key=lambda r: r["variance_kg"])
        elif sort == "surplus":
            rows.sort(key=lambda r: r["variance_kg"], reverse=True)
        else:
            rows.sort(key=lambda r: abs(r["variance_kg"]), reverse=True)

        return {
            "results":              rows,
            "monthly_trends":       self._monthly_trends(rows),
            "waste_type_breakdown": self._waste_breakdown(rows),
            "kpis":                 self._totals(rows),
        }

    def _monthly_trends(self, rows):
        t = {}
        for r in rows:
            m = r["month"]
            t.setdefault(m, {
                "month": m, "total_agreed_weight": 0, "total_actual_weight": 0,
                "variance_kg": 0, "total_trips": 0, "collection_points_covered": 0,
            })
            t[m]["total_agreed_weight"]        += r["total_agreed_weight"]
            t[m]["total_actual_weight"]        += r["total_actual_weight"]
            t[m]["variance_kg"]               += r["variance_kg"]
            t[m]["total_trips"]               += r["total_trips"]
            t[m]["collection_points_covered"] += r["collection_points_covered"]
        return sorted(t.values(), key=lambda x: str(x["month"]))

    def _waste_breakdown(self, rows):
        t = {}
        for r in rows:
            wt = r["waste_type"] or r["waste_type_id"]
            t.setdefault(wt, {
                "waste_type": wt, "total_agreed_weight": 0,
                "total_actual_weight": 0, "variance_kg": 0,
            })
            t[wt]["total_agreed_weight"] += r["total_agreed_weight"]
            t[wt]["total_actual_weight"] += r["total_actual_weight"]
            t[wt]["variance_kg"]         += r["variance_kg"]
        return sorted(t.values(), key=lambda x: abs(x["variance_kg"]), reverse=True)

    def _totals(self, rows):
        agreed  = sum(Decimal(str(r["total_agreed_weight"])) for r in rows)
        actual  = sum(Decimal(str(r["total_actual_weight"])) for r in rows)
        trips   = sum(r["total_trips"] for r in rows)
        points  = sum(r["collection_points_covered"] for r in rows)
        return {
            "total_agreed_weight":           float(_r(agreed)),
            "total_actual_weight":           float(_r(actual)),
            "variance_kg":                   float(_r(actual - agreed)),
            "collection_efficiency_percent": float(_pct(actual, agreed)),
            "average_weight_per_trip":       float(_r(actual / Decimal(trips)) if trips else ZERO),
            "coverage_efficiency_percent":   float(_pct(points, trips)),
            "total_trips":                   trips,
            "collection_points_covered":     points,
            "report_status":                 _status(actual, agreed),
        }

    # ── daily data ───────────────────────────────────────────────────────

    def _daily_data(self, base_qs, month):
        qs = base_qs
        if month:
            try:
                year, mon = month.split("-")
                qs = qs.filter(
                    trip_date__year=int(year),
                    trip_date__month=int(mon),
                )
            except ValueError:
                pass

        # Per-date × per-waste-type breakdown
        breakdown_raw = (
            qs.values("trip_date", "waste_type_id__waste_type_name")
            .annotate(
                actual_weight_kg=Sum("collected_weight_kg"),
                trip_count=Count("unique_id"),
                points_covered=Count("collection_point_id", distinct=True),
            )
            .order_by("trip_date", "waste_type_id__waste_type_name")
        )

        day_wise_breakdown = [
            {
                "date":              str(r["trip_date"]),
                "waste_type":        r["waste_type_id__waste_type_name"] or "Unknown",
                "actual_weight_kg":  float(_r(r["actual_weight_kg"])),
                "agreed_weight_kg":  0.0,   # trip-level agreed not available per waste type
                "trip_count":        int(r["trip_count"] or 0),
                "points_covered":    int(r["points_covered"] or 0),
            }
            for r in breakdown_raw
        ]

        # Day-wise totals (summary / line chart)
        day_totals: dict = {}
        for r in day_wise_breakdown:
            d = r["date"]
            if d not in day_totals:
                day_totals[d] = {"date": d, "collected_weight_kg": 0.0, "trip_count": 0}
            day_totals[d]["collected_weight_kg"] += r["actual_weight_kg"]
            day_totals[d]["trip_count"]          += r["trip_count"]
        day_wise = sorted(day_totals.values(), key=lambda x: x["date"])

        # Waste-type overall totals (pie chart)
        wt_totals: dict = {}
        for r in day_wise_breakdown:
            wt = r["waste_type"]
            if wt not in wt_totals:
                wt_totals[wt] = {"waste_type": wt, "collected_weight_kg": 0.0, "trip_count": 0}
            wt_totals[wt]["collected_weight_kg"] += r["actual_weight_kg"]
            wt_totals[wt]["trip_count"]          += r["trip_count"]
        waste_types = sorted(wt_totals.values(), key=lambda x: x["collected_weight_kg"], reverse=True)

        # Individual daily rows for the table — one row per trip log
        rows_raw = (
            qs.values(
                "unique_id",
                "trip_date",
                "waste_type_id__waste_type_name",
                "collected_weight_kg",
                "panchayat_id__agreed_weight_kg",
                "log_status",
                "collection_point_id",
            )
            .order_by("-trip_date")[:300]
        )

        daily_rows = []
        for r in rows_raw:
            agreed_kg = Decimal(str(r["panchayat_id__agreed_weight_kg"] or 0))
            actual_kg = Decimal(str(r["collected_weight_kg"] or 0))
            var       = actual_kg - agreed_kg
            daily_rows.append({
                "unique_id":                   r["unique_id"],
                "date":                        str(r["trip_date"]),
                "waste_type":                  r["waste_type_id__waste_type_name"] or "—",
                "agreed_weight_kg":            float(_r(agreed_kg)),
                "actual_weight_kg":            float(_r(actual_kg)),
                "variance_kg":                 float(_r(var)),
                "variance_percent":            float(_var_pct(actual_kg, agreed_kg)),
                "report_status":               _status(actual_kg, agreed_kg),
                "total_trips":                 1,
                "collection_points_covered":   1 if r["collection_point_id"] else 0,
            })

        # Daily KPIs
        total_actual  = sum(Decimal(str(r["actual_weight_kg"])) for r in daily_rows)
        total_agreed  = sum(Decimal(str(r["agreed_weight_kg"])) for r in daily_rows)
        total_trips   = sum(r["total_trips"] for r in daily_rows)
        total_points  = sum(r["collection_points_covered"] for r in daily_rows)

        daily_kpis = {
            "total_actual_kg":               float(_r(total_actual)),
            "total_agreed_kg":               float(_r(total_agreed)),
            "variance_kg":                   float(_r(total_actual - total_agreed)),
            "total_trips":                   total_trips,
            "collection_points_covered":     total_points,
            "collection_efficiency_percent": float(_pct(total_actual, total_agreed)),
            "avg_weight_per_trip":           float(
                _r(total_actual / Decimal(total_trips)) if total_trips else ZERO
            ),
        }

        return {
            "day_wise":          day_wise,
            "waste_types":       waste_types,
            "day_wise_breakdown": day_wise_breakdown,
            "daily_rows":        daily_rows,
            "daily_kpis":        daily_kpis,
        }
