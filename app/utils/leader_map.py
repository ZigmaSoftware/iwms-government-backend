"""
Shared payload builder for the State / District leader dashboard maps.

The frontend draws district boundaries from bundled per-state GeoJSON, and
overlays every ULB (corporation / municipality / town panchayat) and RLB
(panchayat union / panchayat) from the masters using each record's own
`coordinates` list ([{latitude, longitude}, ...] — a boundary when it has
3+ points, a location otherwise). Collection figures come from DailyTripLog,
which carries a flat id column for every geo level (see
DailyTripLog.copy_flat_geo()), so each level is aggregated directly.

Query params:
  month   YYYY-MM — defaults to the current month
  source  all (default) | bin | household
"""
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count
from django.utils import timezone

from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.ward import Ward
from app.viewsets.statebody.statebody_waste_comparison_viewset import weight_annotation

TWO = Decimal("0.01")

# (type key, category, model, name field, DailyTripLog column)
LOCAL_BODY_TYPES = (
    ("corporation", "ulb", Corporation, "corporation_name", "corporation_id"),
    ("municipality", "ulb", Municipality, "municipality_name", "municipality_id"),
    ("town_panchayat", "ulb", TownPanchayat, "town_panchayat_name", "town_panchayat_id"),
    ("panchayat_union", "rlb", PanchayatUnion, "union_name", "panchayat_union_id"),
    ("panchayat", "rlb", Panchayat, "panchayat_name", "panchayat_id"),
)


def _num(value):
    return float(Decimal(str(value or 0)).quantize(TWO, rounding=ROUND_HALF_UP))


def _clean_coordinates(raw):
    """[{latitude, longitude}] -> [[lat, lng], ...], dropping bad points."""
    points = []
    for p in raw if isinstance(raw, list) else []:
        try:
            lat, lng = float(p["latitude"]), float(p["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            points.append([lat, lng])
    return points


def parse_params(request):
    month = request.query_params.get("month") or timezone.localdate().strftime("%Y-%m")
    try:
        year, mon = (int(x) for x in month.split("-"))
    except (ValueError, AttributeError):
        today = timezone.localdate()
        year, mon = today.year, today.month
    source = (request.query_params.get("source") or "all").lower()
    if source not in ("all", "bin", "household"):
        source = "all"
    return year, mon, source


def _stats_by(qs, column, source):
    rows = (
        qs.exclude(**{f"{column}__isnull": True}).exclude(**{column: ""})
        .values(column)
        .annotate(
            weight=weight_annotation(source),
            trips=Count("unique_id", distinct=True),
            points=Count("collection_point_id", distinct=True),
        )
    )
    return {
        r[column]: {"weight": _num(r["weight"]), "trips": r["trips"], "points": r["points"]}
        for r in rows
    }


EMPTY = {"weight": 0.0, "trips": 0, "points": 0}


def build_map_payload(request, *, state_id, district_id=None):
    """Districts + local bodies (with this month's collection stats) for one
    state, or — when district_id is given — for that single district."""
    year, mon, source = parse_params(request)

    scope = {"state_id": state_id, "is_deleted": False}
    if district_id:
        scope["district_id"] = district_id

    trips = DailyTripLog.objects.filter(
        is_deleted=False,
        state_id=state_id,
        trip_date__year=year,
        trip_date__month=mon,
        log_status__in=[DailyTripLog.LOG_STATUS_SUBMITTED, DailyTripLog.LOG_STATUS_VERIFIED],
    )
    if district_id:
        trips = trips.filter(district_id=district_id)

    district_qs = District.objects.filter(state_id=state_id, is_deleted=False)
    if district_id:
        district_qs = district_qs.filter(unique_id=district_id)
    district_stats = _stats_by(trips, "district_id", source)
    districts = [
        {
            "district_id": d.unique_id,
            "name": d.name,
            "is_active": d.is_active,
            "coordinates": _clean_coordinates(d.coordinates),
            **district_stats.get(d.unique_id, EMPTY),
        }
        for d in district_qs.order_by("name")
    ]

    local_bodies = []
    ward_scope = {"state_id": state_id, "is_deleted": False}
    if district_id:
        ward_scope["district_id"] = district_id
    for type_key, category, model, name_field, trip_column in LOCAL_BODY_TYPES:
        stats = _stats_by(trips, trip_column, source)
        # wards hang off ULBs through the same flat id column DailyTripLog uses
        wards = (
            dict(
                Ward.objects.filter(**ward_scope).exclude(**{f"{trip_column}__isnull": True})
                .values_list(trip_column).annotate(n=Count("unique_id"))
            )
            if category == "ulb" else {}
        )
        for obj in model.objects.filter(**scope).order_by(name_field):
            local_bodies.append({
                "id": obj.unique_id,
                "type": type_key,
                "category": category,
                "name": getattr(obj, name_field),
                "district_id": obj.district_id,
                "is_active": obj.is_active,
                "coordinates": _clean_coordinates(obj.coordinates),
                "wards": wards.get(obj.unique_id, 0) if category == "ulb" else None,
                **stats.get(obj.unique_id, EMPTY),
            })

    agg = trips.aggregate(
        weight=weight_annotation(source),
        trips=Count("unique_id", distinct=True),
        points=Count("collection_point_id", distinct=True),
    )
    totals = {"weight": _num(agg["weight"]), "trips": agg["trips"], "points": agg["points"]}
    return {
        "month": f"{year:04d}-{mon:02d}",
        "source": source,
        "districts": districts,
        "local_bodies": local_bodies,
        "totals": totals,
    }
