"""
Shared payload builder for the State / District leader dashboard side panels
(period KPIs, 7-day trend, waste-type split, grievances, fleet).

Everything is computed from live records, scoped server-side to the leader's
own state (and district, for the district portal):
  - collection: DailyTripLog (Submitted / Verified), per-waste-type weight
    via bulk_waste_type_rows_for_trip_assignments (a trip can span several
    waste types; trip counts always come from DailyTripLog itself)
  - grievances: ComplaintTicket by ComplaintStatus
  - fleet:      VehicleCreation + open VehicleBreakdown reports

Query params:
  source  all (default) | bin | household
"""
import datetime
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count
from django.utils import timezone

from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.utils.leader_map import LOCAL_BODY_TYPES
from app.utils.waste_type_breakdown import bulk_waste_type_rows_for_trip_assignments
from app.viewsets.statebody.statebody_waste_comparison_viewset import weight_annotation

TWO = Decimal("0.01")


def _num(value):
    return float(Decimal(str(value or 0)).quantize(TWO, rounding=ROUND_HALF_UP))


def _pct_change(current, previous):
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


def _period_totals(qs, source, start, end):
    agg = qs.filter(trip_date__gte=start, trip_date__lte=end).aggregate(
        weight=weight_annotation(source),
        trips=Count("unique_id", distinct=True),
    )
    return {"weight": _num(agg["weight"]), "trips": agg["trips"]}


def _period(qs, source, start, end, prev_start, prev_end):
    cur = _period_totals(qs, source, start, end)
    prev = _period_totals(qs, source, prev_start, prev_end)
    return {
        **cur,
        "from": str(start),
        "to": str(end),
        "previous_weight": prev["weight"],
        "change_percent": _pct_change(cur["weight"], prev["weight"]),
    }


def _waste_type_split(qs, source):
    """[{waste_type_id, waste_type, weight, share_percent}] for qs's trips."""
    ids = list(qs.values_list("trip_assignment_id", flat=True).distinct())
    totals, names = defaultdict(Decimal), {}
    for row in bulk_waste_type_rows_for_trip_assignments(ids, source=source):
        totals[row["waste_type_id"]] += row["weight_kg"]
        names[row["waste_type_id"]] = row["waste_type_name"] or row["waste_type_id"]
    grand = sum(totals.values(), Decimal("0"))
    rows = [
        {
            "waste_type_id": wid,
            "waste_type": names[wid],
            "weight": _num(w),
            "share_percent": _num(w / grand * 100) if grand else 0.0,
        }
        for wid, w in totals.items()
    ]
    return sorted(rows, key=lambda r: r["weight"], reverse=True)


def _daily_trend(qs, source, days):
    """One row per day: total weight / trips (from DailyTripLog) plus the
    per-waste-type split (from the collection records)."""
    by_day = {
        r["trip_date"]: r
        for r in qs.values("trip_date").annotate(
            weight=weight_annotation(source), trips=Count("unique_id", distinct=True)
        )
    }
    ids = list(qs.values_list("trip_assignment_id", flat=True).distinct())
    split = defaultdict(lambda: defaultdict(Decimal))
    names = {}
    for row in bulk_waste_type_rows_for_trip_assignments(ids, source=source, extra_group_by=("trip_date",)):
        names[row["waste_type_id"]] = row["waste_type_name"] or row["waste_type_id"]
        split[row["trip_date"]][row["waste_type_id"]] += row["weight_kg"]
    out = []
    for d in days:
        r = by_day.get(d, {})
        out.append({
            "date": str(d),
            "weight": _num(r.get("weight")),
            "trips": r.get("trips", 0),
            "by_type": {names[wid]: _num(w) for wid, w in split.get(d, {}).items()},
        })
    return out, sorted(set(names.values()))


def build_summary(request, *, state_id, district_id=None):
    source = (request.query_params.get("source") or "all").lower()
    if source not in ("all", "bin", "household"):
        source = "all"

    today = timezone.localdate()
    scope = {"state_id": state_id}
    if district_id:
        scope["district_id"] = district_id

    trips = DailyTripLog.objects.filter(
        is_deleted=False,
        log_status__in=[DailyTripLog.LOG_STATUS_SUBMITTED, DailyTripLog.LOG_STATUS_VERIFIED],
        **scope,
    )

    # ── periods: today / last 7 days / month-to-date, each vs the period before
    week_start = today - datetime.timedelta(days=6)
    month_start = today.replace(day=1)
    prev_month_end = month_start - datetime.timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    prev_month_same_day = min(prev_month_end, prev_month_start + datetime.timedelta(days=today.day - 1))
    yesterday = today - datetime.timedelta(days=1)
    periods = {
        "today": _period(trips, source, today, today, yesterday, yesterday),
        "week": _period(
            trips, source, week_start, today,
            week_start - datetime.timedelta(days=7), week_start - datetime.timedelta(days=1),
        ),
        "month": _period(trips, source, month_start, today, prev_month_start, prev_month_same_day),
    }

    # ── 7-day trend + waste-type splits
    days = [week_start + datetime.timedelta(days=i) for i in range(7)]
    trend, waste_types = _daily_trend(trips.filter(trip_date__gte=week_start, trip_date__lte=today), source, days)
    today_qs = trips.filter(trip_date=today)
    month_qs = trips.filter(trip_date__gte=month_start, trip_date__lte=today)

    # ── who reported today: districts (state) / local bodies (district)
    if district_id:
        reporting = sum(
            today_qs.exclude(**{f"{col}__isnull": True}).exclude(**{col: ""}).values(col).distinct().count()
            for _t, _c, _m, _n, col in LOCAL_BODY_TYPES
        )
    else:
        reporting = today_qs.exclude(district_id__isnull=True).exclude(district_id="").values("district_id").distinct().count()

    # ── grievances (all open + this month's intake), by status
    tickets = ComplaintTicket.objects.filter(is_deleted=False, **scope)
    status_rows = list(tickets.values("status_id").annotate(n=Count("unique_id")))
    statuses = {
        s.unique_id: s
        for s in ComplaintStatus.objects.filter(unique_id__in=[r["status_id"] for r in status_rows])
    }
    by_status = sorted(
        (
            {
                "status": getattr(statuses.get(r["status_id"]), "status_name", None) or r["status_id"],
                "is_final": bool(getattr(statuses.get(r["status_id"]), "is_final", False)),
                "count": r["n"],
                "_order": getattr(statuses.get(r["status_id"]), "sort_order", 999),
            }
            for r in status_rows
        ),
        key=lambda r: r["_order"],
    )
    for r in by_status:
        r.pop("_order")
    grievances = {
        "total": sum(r["count"] for r in by_status),
        "open": sum(r["count"] for r in by_status if not r["is_final"]),
        "this_month": tickets.filter(created__date__gte=month_start).count(),
        "by_status": by_status,
    }

    # ── fleet
    vehicles = VehicleCreation.objects.filter(is_deleted=False, **scope)
    total_vehicles = vehicles.count()
    active_vehicles = vehicles.filter(is_active=True).count()
    on_trip_today = today_qs.values("vehicle_id").distinct().count()
    open_breakdowns = VehicleBreakdown.objects.filter(
        is_deleted=False, status=VehicleBreakdown.STATUS_REPORTED, **scope
    ).count()
    fleet = {
        "total": total_vehicles,
        "active": active_vehicles,
        "inactive": total_vehicles - active_vehicles,
        "on_trip_today": on_trip_today,
        "open_breakdowns": open_breakdowns,
    }

    return {
        "as_of": str(today),
        "source": source,
        "periods": periods,
        "reporting_today": reporting,
        "trend": trend,
        "waste_types": waste_types,
        "today_breakdown": _waste_type_split(today_qs, source),
        "month_breakdown": _waste_type_split(month_qs, source),
        "grievances": grievances,
        "fleet": fleet,
    }
