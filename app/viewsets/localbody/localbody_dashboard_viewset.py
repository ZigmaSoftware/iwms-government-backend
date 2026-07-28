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

from app.models.masters.leader_management.panchayat_leader_login import PanchayatLeaderLogin
from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.utils.waste_type_breakdown import bulk_waste_type_rows_for_trip_assignments


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
        ).select_related("collection_point_id").prefetch_related("waste_types")

        monthly_data = self._monthly_report(base_qs, panchayat, month, sort)
        daily_data   = self._daily_data(base_qs, panchayat, month)

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

        agreed_per_day = Decimal(str(getattr(panchayat, "agreed_weight_kg", 0) or 0))
        panchayat_uid  = panchayat.unique_id
        panchayat_name = getattr(panchayat, "panchayat_name", "") or ""

        # Per-waste-type weight, computed from the actual collection records
        # (a trip can legitimately span more than one waste type).
        trip_assignment_ids = list(qs.values_list("trip_assignment_id_id", flat=True).distinct())
        wt_rows = bulk_waste_type_rows_for_trip_assignments(
            trip_assignment_ids, source="all", extra_group_by=("trip_date",),
        )
        trip_log_info = qs.values("trip_assignment_id_id", "trip_date")
        info_by_assignment = {}
        for r in trip_log_info:
            info_by_assignment.setdefault(r["trip_assignment_id_id"], []).append(r)

        bucket_totals = {}  # (year, month, waste_type_id) -> accumulator
        for wt_row in wt_rows:
            infos = info_by_assignment.get(wt_row["trip_assignment_id"], [])
            for info in infos:
                if str(info["trip_date"]) != str(wt_row["trip_date"]):
                    continue
                year_val, month_val = info["trip_date"].year, info["trip_date"].month
                key = (year_val, month_val, wt_row["waste_type_id"])
                bucket = bucket_totals.setdefault(key, {
                    "year": year_val, "month": month_val,
                    "waste_type_id": wt_row["waste_type_id"],
                    "waste_type_name": wt_row["waste_type_name"],
                    "weight_kg": ZERO,
                    "trip_assignment_ids": set(),
                })
                bucket["weight_kg"] += wt_row["weight_kg"]
                bucket["trip_assignment_ids"].add(wt_row["trip_assignment_id"])

        rows = []
        for (year_val, month_val, waste_type_id), bucket in bucket_totals.items():
            month_str  = f"{year_val}-{month_val:02d}"
            trip_days  = len({
                info["trip_date"] for aid in bucket["trip_assignment_ids"]
                for info in info_by_assignment.get(aid, [])
            })
            agreed = agreed_per_day * Decimal(str(trip_days))
            actual = bucket["weight_kg"]
            var    = actual - agreed
            trips  = len(bucket["trip_assignment_ids"])

            rows.append({
                "unique_id":                    f"MWR-{month_str}-{panchayat_uid}-{waste_type_id}",
                "month":                        month_str,
                "panchayat_id":                 panchayat_uid,
                "panchayat_name":               panchayat_name,
                "waste_type_id":                waste_type_id,
                "waste_type":                   bucket["waste_type_name"] or "—",
                "total_agreed_weight":          float(_r(agreed)),
                "total_actual_weight":          float(_r(actual)),
                "variance_kg":                  float(_r(var)),
                "variance_percent":             float(_var_pct(actual, agreed)),
                "report_status":                _status(actual, agreed),
                "total_trips":                  trips,
                # not meaningfully splittable per waste type — reported at
                # the month level instead (see monthly_totals below).
                "collection_points_covered":    0,
                "collection_efficiency_percent": float(_pct(actual, agreed)),
                "coverage_efficiency_percent":  0.0,
                "average_weight_per_trip":      float(_r(actual / Decimal(trips)) if trips else ZERO),
            })

        if sort == "deficit":
            rows.sort(key=lambda r: r["variance_kg"])
        elif sort == "surplus":
            rows.sort(key=lambda r: r["variance_kg"], reverse=True)
        else:
            rows.sort(key=lambda r: abs(r["variance_kg"]), reverse=True)

        # Month-level totals (trip-log level, waste-type-independent) so a
        # multi-waste-type trip is never double counted in trends/KPIs.
        monthly_grouped = qs.values("trip_date__year", "trip_date__month").annotate(
            total_actual_weight=Sum("collected_weight_kg"),
            total_trips=Count("unique_id", distinct=True),
            collection_points=Count("collection_point_id", distinct=True),
            distinct_trip_days=Count("trip_date", distinct=True),
        )
        monthly_totals = []
        for row in monthly_grouped:
            month_str  = f"{row['trip_date__year']}-{row['trip_date__month']:02d}"
            trip_days  = int(row["distinct_trip_days"] or 0)
            agreed     = agreed_per_day * Decimal(str(trip_days))
            actual     = Decimal(str(row["total_actual_weight"] or 0))
            trips      = int(row["total_trips"] or 0)
            points     = int(row["collection_points"] or 0)
            monthly_totals.append({
                "month": month_str,
                "total_agreed_weight": float(_r(agreed)),
                "total_actual_weight": float(_r(actual)),
                "variance_kg": float(_r(actual - agreed)),
                "total_trips": trips,
                "collection_points_covered": points,
                "collection_efficiency_percent": float(_pct(actual, agreed)),
                "coverage_efficiency_percent": float(_pct(points, trips)),
            })

        return {
            "results":              rows,
            "monthly_trends":       self._monthly_trends(monthly_totals),
            "waste_type_breakdown": self._waste_breakdown(rows),
            "kpis":                 self._totals(monthly_totals),
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

    def _daily_data(self, base_qs, panchayat, month):
        agreed_per_day = Decimal(str(getattr(panchayat, "agreed_weight_kg", 0) or 0))

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

        # Per-date × per-waste-type breakdown, from actual collection records
        # (a trip can legitimately span more than one waste type).
        trip_assignment_ids = list(qs.values_list("trip_assignment_id_id", flat=True).distinct())
        wt_rows = bulk_waste_type_rows_for_trip_assignments(
            trip_assignment_ids, source="all", extra_group_by=("trip_date",),
        )
        trip_log_info = qs.values("trip_assignment_id_id", "trip_date", "collection_point_id")
        info_by_assignment = {}
        for r in trip_log_info:
            info_by_assignment.setdefault(r["trip_assignment_id_id"], []).append(r)

        breakdown_totals = {}  # (date, waste_type_name) -> accumulator
        for wt_row in wt_rows:
            infos = info_by_assignment.get(wt_row["trip_assignment_id"], [])
            for info in infos:
                if str(info["trip_date"]) != str(wt_row["trip_date"]):
                    continue
                key = (info["trip_date"], wt_row["waste_type_name"])
                bucket = breakdown_totals.setdefault(key, {
                    "date": info["trip_date"],
                    "waste_type": wt_row["waste_type_name"] or "Unknown",
                    "actual_weight_kg": ZERO,
                    "trip_assignment_ids": set(),
                    "collection_point_ids": set(),
                })
                bucket["actual_weight_kg"] += wt_row["weight_kg"]
                bucket["trip_assignment_ids"].add(wt_row["trip_assignment_id"])
                if info["collection_point_id"]:
                    bucket["collection_point_ids"].add(info["collection_point_id"])

        day_wise_breakdown = sorted(
            (
                {
                    "date":              str(bucket["date"]),
                    "waste_type":        bucket["waste_type"],
                    "actual_weight_kg":  float(_r(bucket["actual_weight_kg"])),
                    "agreed_weight_kg":  float(_r(agreed_per_day)),
                    "trip_count":        len(bucket["trip_assignment_ids"]),
                    "points_covered":    len(bucket["collection_point_ids"]),
                }
                for bucket in breakdown_totals.values()
            ),
            key=lambda r: (r["date"], r["waste_type"]),
        )

        # Day-wise totals (summary / line chart) — trip-log level, so a
        # multi-waste-type trip is counted once, not once per waste type.
        day_level = qs.values("trip_date").annotate(
            collected_weight_kg=Sum("collected_weight_kg"),
            trip_count=Count("unique_id", distinct=True),
        )
        day_totals: dict = {
            str(r["trip_date"]): {
                "date": str(r["trip_date"]),
                "collected_weight_kg": float(_r(r["collected_weight_kg"])),
                "trip_count": int(r["trip_count"] or 0),
            }
            for r in day_level
        }
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
            qs.prefetch_related("waste_types")
            .order_by("-trip_date")[:300]
        )

        daily_rows = []
        for log in rows_raw:
            actual_kg = Decimal(str(log.collected_weight_kg or 0))
            variance  = actual_kg - agreed_per_day
            waste_type_names = [wt.waste_type_name for wt in log.waste_types.all()]
            daily_rows.append({
                "unique_id":                   log.unique_id,
                "date":                        str(log.trip_date),
                "waste_type":                  ", ".join(waste_type_names) or "—",
                "agreed_weight_kg":            float(_r(agreed_per_day)),
                "actual_weight_kg":            float(_r(actual_kg)),
                "variance_kg":                 float(_r(variance)),
                "variance_percent":            float(_var_pct(actual_kg, agreed_per_day)),
                "report_status":               _status(actual_kg, agreed_per_day),
                "total_trips":                 1,
                "collection_points_covered":   1 if log.collection_point_id_id else 0,
            })

        # Daily KPIs — use agreed_per_day × distinct trip dates (not sum of per-row agreed)
        total_actual       = sum(Decimal(str(r["actual_weight_kg"])) for r in daily_rows)
        distinct_trip_days = len(day_wise)   # number of unique dates with trips
        total_agreed       = agreed_per_day * Decimal(str(distinct_trip_days))
        total_trips        = sum(r["total_trips"] for r in daily_rows)
        total_points       = sum(r["collection_points_covered"] for r in daily_rows)

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
