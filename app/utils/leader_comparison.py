"""
District Leader — Monthly / Daily waste comparison, per local body.

The district counterpart of StateMonthly/DailyWasteComparisonViewSet: scoped
server-side to the leader's own district and grouped by the trip's local
body (DailyTripLog carries one flat id column per local-body type — see
DailyTripLog.copy_flat_geo()) instead of by district.

Query params:
  source         bin (default) | household | all
  sort           weight (default) | trips      (detailed rows order)
  month          YYYY-MM — monthly: optional (omitted = every month on
                 record); daily: defaults to the current month
  date           YYYY-MM-DD — daily only, narrows to one day
  local_body_id  optional — narrow to one ULB / RLB of the district

Response (both granularities):
  kpis, trends [{period, total_actual_weight, total_trips}],
  waste_type_breakdown, comparison (one row per local body), results
  (period × local body × waste type).
"""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Q
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.utils.leader_map import LOCAL_BODY_TYPES
from app.utils.waste_type_breakdown import bulk_waste_type_rows_for_trip_assignments
from app.viewsets.statebody.statebody_waste_comparison_viewset import weight_annotation

TWO = Decimal("0.01")
ZERO = Decimal("0")
LB_COLUMNS = tuple(col for _t, _c, _m, _n, col in LOCAL_BODY_TYPES)
TYPE_BY_COLUMN = {col: t for t, _c, _m, _n, col in LOCAL_BODY_TYPES}
RESULTS_CAP = 2000


def _round(v):
    return float(Decimal(str(v or 0)).quantize(TWO, rounding=ROUND_HALF_UP))


# most specific first: should a trip ever carry both a village panchayat
# and its union, it belongs to the panchayat
ATTRIBUTION_ORDER = ("panchayat_id", "town_panchayat_id", "municipality_id", "corporation_id", "panchayat_union_id")


def _local_body_of(row):
    """(type, id) of the local body a DailyTripLog row belongs to."""
    for col in ATTRIBUTION_ORDER:
        if row.get(col):
            return TYPE_BY_COLUMN[col], row[col]
    return None, None


def _names(ids_by_type):
    out = {}
    for type_key, _cat, model, name_field, _col in LOCAL_BODY_TYPES:
        ids = ids_by_type.get(type_key)
        if ids:
            out.update(dict(model.objects.filter(unique_id__in=ids).values_list("unique_id", name_field)))
    return out


def build_lb_comparison(request, *, district_id, granularity):
    params = request.query_params
    source = (params.get("source") or "bin").lower()
    if source not in ("all", "bin", "household"):
        source = "bin"

    qs = DailyTripLog.objects.filter(
        is_deleted=False,
        district_id=district_id,
        log_status__in=[DailyTripLog.LOG_STATUS_SUBMITTED, DailyTripLog.LOG_STATUS_VERIFIED],
    )

    month = params.get("month")
    date = params.get("date") if granularity == "day" else None
    if date:
        qs = qs.filter(trip_date=date)
    else:
        if not month and granularity == "day":
            month = timezone.localdate().strftime("%Y-%m")
        if month:
            try:
                year, mon = (int(x) for x in month.split("-"))
                qs = qs.filter(trip_date__year=year, trip_date__month=mon)
            except (ValueError, AttributeError):
                pass

    local_body_id = params.get("local_body_id")
    if local_body_id:
        qs = qs.filter(Q(**{LB_COLUMNS[0]: local_body_id}) | Q(**{LB_COLUMNS[1]: local_body_id})
                       | Q(**{LB_COLUMNS[2]: local_body_id}) | Q(**{LB_COLUMNS[3]: local_body_id})
                       | Q(**{LB_COLUMNS[4]: local_body_id}))

    period_of = (lambda d: d.strftime("%Y-%m")) if granularity == "month" else (lambda d: str(d))

    # ── trip-log level (a trip counts once even across waste types) ──────
    per_day_lb = list(
        qs.values("trip_date", *LB_COLUMNS).annotate(
            weight=weight_annotation(source), trips=Count("unique_id", distinct=True)
        )
    )
    trends = defaultdict(lambda: {"total_actual_weight": ZERO, "total_trips": 0})
    for r in per_day_lb:
        t = trends[period_of(r["trip_date"])]
        t["total_actual_weight"] += Decimal(str(r["weight"] or 0))
        t["total_trips"] += r["trips"]

    per_lb = list(
        qs.values(*LB_COLUMNS).annotate(
            weight=weight_annotation(source),
            trips=Count("unique_id", distinct=True),
            points=Count("collection_point_id", distinct=True),
        )
    )
    lb_rows = {}
    for r in per_lb:
        t, lid = _local_body_of(r)
        if not lid:
            continue
        acc = lb_rows.setdefault(lid, {"type": t, "weight": ZERO, "trips": 0, "points": 0})
        acc["weight"] += Decimal(str(r["weight"] or 0))
        acc["trips"] += r["trips"]
        acc["points"] += r["points"]

    # ── per waste type, from the collection records ──────────────────────
    ids = list(qs.values_list("trip_assignment_id", flat=True).distinct())
    wt_rows = bulk_waste_type_rows_for_trip_assignments(ids, source=source, extra_group_by=("trip_date", *LB_COLUMNS))
    buckets = {}
    type_totals = defaultdict(lambda: {"name": "", "weight": ZERO})
    for r in wt_rows:
        t, lid = _local_body_of(r)
        if not lid or not r.get("trip_date"):
            continue
        key = (period_of(r["trip_date"]), lid, r["waste_type_id"])
        b = buckets.setdefault(key, {"type": t, "name": r["waste_type_name"] or r["waste_type_id"], "weight": ZERO, "trips": set()})
        b["weight"] += r["weight_kg"]
        b["trips"].add(r["trip_assignment_id"])
        tt = type_totals[r["waste_type_id"]]
        tt["name"] = r["waste_type_name"] or r["waste_type_id"]
        tt["weight"] += r["weight_kg"]

    ids_by_type = defaultdict(set)
    for lid, acc in lb_rows.items():
        ids_by_type[acc["type"]].add(lid)
    for (_p, lid, _w), b in buckets.items():
        ids_by_type[b["type"]].add(lid)
    names = _names(ids_by_type)

    comparison = sorted(
        (
            {
                "id": lid,
                "type": acc["type"],
                "name": names.get(lid, lid),
                "total_actual_weight": _round(acc["weight"]),
                "total_trips": acc["trips"],
                "collection_points_covered": acc["points"],
                "average_weight_per_trip": _round(acc["weight"] / acc["trips"]) if acc["trips"] else 0.0,
            }
            for lid, acc in lb_rows.items()
        ),
        key=lambda r: r["total_actual_weight"],
        reverse=True,
    )

    results = [
        {
            "unique_id": f"DLBC-{period}-{lid}-{wid}",
            "period": period,
            "id": lid,
            "type": b["type"],
            "name": names.get(lid, lid),
            "waste_type_id": wid,
            "waste_type": b["name"],
            "total_actual_weight": _round(b["weight"]),
            "total_trips": len(b["trips"]),
        }
        for (period, lid, wid), b in buckets.items()
    ]
    if (params.get("sort") or "weight").lower() == "trips":
        results.sort(key=lambda r: (r["total_trips"], r["total_actual_weight"]), reverse=True)
    else:
        results.sort(key=lambda r: r["total_actual_weight"], reverse=True)

    grand = sum((tt["weight"] for tt in type_totals.values()), ZERO)
    breakdown = sorted(
        (
            {
                "waste_type_id": wid,
                "waste_type": tt["name"],
                "total_actual_weight": _round(tt["weight"]),
                "share_percent": _round(tt["weight"] / grand * 100) if grand else 0.0,
            }
            for wid, tt in type_totals.items()
        ),
        key=lambda r: r["total_actual_weight"],
        reverse=True,
    )

    agg = qs.aggregate(
        weight=weight_annotation(source),
        trips=Count("unique_id", distinct=True),
        points=Count("collection_point_id", distinct=True),
    )
    total_weight, total_trips = Decimal(str(agg["weight"] or 0)), agg["trips"]
    return {
        "source": source,
        "granularity": granularity,
        "kpis": {
            "total_actual_weight": _round(total_weight),
            "total_trips": total_trips,
            "collection_points_covered": agg["points"],
            "average_weight_per_trip": _round(total_weight / total_trips) if total_trips else 0.0,
            "waste_type_count": len(type_totals),
            "local_body_count": len(lb_rows),
        },
        "trends": [
            {"period": p, "total_actual_weight": _round(v["total_actual_weight"]), "total_trips": v["total_trips"]}
            for p, v in sorted(trends.items())
        ],
        "waste_type_breakdown": breakdown,
        "comparison": comparison,
        "results": results[:RESULTS_CAP],
        "results_total": len(results),
    }
