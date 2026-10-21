"""KPIs shared by the Admin and Superadmin dashboards.

Ported from the private (company/project) build. Here every operational row
carries flat geography columns instead — state_id, district_id, area_type_id
and exactly one local-body id (corporation_id / municipality_id /
town_panchayat_id / panchayat_union_id / panchayat_id) — so a `Scope` is the
requester (whose StaffDataScope caps what they may see) plus an optional
selection of districts, local bodies and wards, and an inclusive date range.

Models without geography of their own (household stops, collection points,
retrip requests, face attendance) are scoped through the trips or staff they
belong to.

Day buckets for DateTimeFields are computed in Python from an aware
[start, end) window rather than with TruncDate / `__date`: on MySQL those
need the server's time zone tables, which a fresh install does not load.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date

from app.models.core_modules.attendance.daily_attendance_reg import DailyAttendanceReg
from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.subcategory_master import ComplaintSubcategory
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.core_modules.daily_operations.daily_trip_household_collection import (
    DailyTripHouseholdCollection,
)
from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.models.core_modules.daily_operations.secondary_bin_collection_event import (
    BinCollectionEvent,
)
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown
from app.models.core_modules.daily_operations.waste_collection import WasteCollection
from app.models.core_modules.schedule_setup.alternative_staff_template import (
    AlternativeStaffTemplate,
)
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.customer_masters.customer_access_configuration import (
    CustomerAccessConfiguration,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.models.masters.district import District
from app.models.masters.leader_management.district_leader_login import DistrictLeaderLogin
from app.models.masters.leader_management.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.leader_management.state_leader_login import StateLeaderLogin
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.transport_masters.fuel import Fuel
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.masters.waste_masters.bins import Bins
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.masters.ward import Ward
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.models.superadmin.role_management.governmentStaffUserType import (
    GovernmentStaffUserType,
)
from app.models.superadmin.role_management.staffUserType import StaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
)
from app.models.superadmin.staff_management.staff_data_scope import StaffDataScope
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.utils.hierarchy import (
    STAFF_GEO_LEVEL_FIELDS,
    STAFF_LOCAL_BODY_M2M_LEVELS,
    _staff_scope,
    filter_flat_geo_queryset_by_requester_scope,
)
from app.utils.plain_ref import json_contains_any

MAX_RANGE_DAYS = 366

# (row column, master model, name field, label) for each local-body level.
LOCAL_BODY_LEVELS = (
    ("corporation_id", Corporation, "corporation_name", "Corporation"),
    ("municipality_id", Municipality, "municipality_name", "Municipality"),
    ("town_panchayat_id", TownPanchayat, "town_panchayat_name", "Town Panchayat"),
    ("panchayat_union_id", PanchayatUnion, "union_name", "Panchayat Union"),
    ("panchayat_id", Panchayat, "panchayat_name", "Panchayat"),
)
LOCAL_BODY_FIELDS = tuple(field for field, *_ in LOCAL_BODY_LEVELS)


# ------------------------------------------------------------------ scope

@dataclass(frozen=True, eq=False)
class Scope:
    start: date
    end: date  # inclusive
    # The requester; their StaffDataScope caps every query. None = unrestricted
    # (the superadmin endpoint).
    user: object = None
    state_ids: tuple = ()
    district_ids: tuple = ()
    # {row column: ids}, e.g. {"corporation_id": ("CORP-1",)}. Several levels
    # may be picked at once; rows matching any of them are kept.
    local_bodies: tuple = ()  # ((field, (ids...)), ...)
    ward_ids: tuple = ()

    @property
    def days(self):
        return [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]

    @property
    def window(self):
        """Aware [start, end) datetimes covering the date range."""
        tz = timezone.get_current_timezone()
        return (
            timezone.make_aware(datetime.combine(self.start, time.min), tz),
            timezone.make_aware(datetime.combine(self.end + timedelta(days=1), time.min), tz),
        )


def parse_range(params):
    """`date` (one day) or `from_date`/`to_date` (inclusive). Defaults to
    today. The range is clamped to MAX_RANGE_DAYS ending on `to_date`."""
    single = _parse(params.get("date"))
    if single:
        return single, single
    start = _parse(params.get("from_date"))
    end = _parse(params.get("to_date")) or timezone.localdate()
    start = start or end
    if start > end:
        start, end = end, start
    if (end - start).days >= MAX_RANGE_DAYS:
        start = end - timedelta(days=MAX_RANGE_DAYS - 1)
    return start, end


def _parse(value):
    try:
        return parse_date((value or "").strip()) if value else None
    except (TypeError, ValueError):
        return None


def has_field(model, name):
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def live(qs):
    """Rows that are not soft-deleted."""
    return qs.filter(is_deleted=False) if has_field(qs.model, "is_deleted") else qs


# The location masters describe one level of the hierarchy themselves, so
# that level's id is their own unique_id (a Corporation has no
# `corporation_id`). Same maps as DashboardSummaryViewSet's filter lists.
_PARENT_COLUMNS = {"area_type_id": "area_type_id", "district_id": "district_id", "state_id": "state_id"}
MASTER_GEO_COLUMNS = {
    State: {"state_id": "unique_id"},
    District: {"district_id": "unique_id", "state_id": "state_id"},
    AreaType: {"area_type_id": "unique_id", "district_id": "district_id", "state_id": "state_id"},
    **{model: {field: "unique_id", **_PARENT_COLUMNS} for field, model, *_ in LOCAL_BODY_LEVELS},
}
LOCAL_BODY_MODELS = {model for _f, model, *_ in LOCAL_BODY_LEVELS}

# Config tables that belong to a staff member and carry no columns of their
# own: scoped through the scoped staff list.
STAFF_LINKED_MODELS = (StaffDataScope, StaffAccessConfiguration)


def geo_columns(model):
    """{flat-geo field: column on `model`}, or None when the model carries no
    geography (it is then scoped by the caller through its trip / staff)."""
    if model in MASTER_GEO_COLUMNS:
        return MASTER_GEO_COLUMNS[model]
    columns = {f: f for f in STAFF_GEO_LEVEL_FIELDS if has_field(model, f)}
    return columns or None


def _granted_local_bodies(user):
    """{flat-geo field: granted ids} for a staff scoped to specific local
    bodies — the local-body columns plus the parents of those bodies — or
    None when the scope is a whole district / state (or the user is a
    super admin). Cached on the user for the request."""
    if getattr(user, "is_superuser", False):
        return None
    if hasattr(user, "_dashboard_granted_bodies"):
        return user._dashboard_granted_bodies
    granted = None
    data_scope = _staff_scope(user)
    if data_scope is not None:
        levels = {
            field: set(getattr(data_scope, m2m).values_list("unique_id", flat=True))
            for _level, field, m2m in STAFF_LOCAL_BODY_M2M_LEVELS
        }
        if any(levels.values()):
            granted = {**levels, "district_id": set(), "area_type_id": set(), "state_id": set()}
            for field, model, *_ in LOCAL_BODY_LEVELS:
                for parents in model.objects.filter(unique_id__in=levels[field]).values(
                    "district_id", "area_type_id", "state_id",
                ):
                    for key, value in parents.items():
                        if value:
                            granted[key].add(value)
    try:
        user._dashboard_granted_bodies = granted
    except AttributeError:
        pass
    return granted


def _cap_location_master(qs, user, columns):
    """The shared requester filter only sees the level it is handed, so for
    a location master of a local-body-scoped staff (e.g. the Municipality or
    District master of a staff granted two corporations) it finds no ids and
    falls back to the scope's empty district — every row. Cap those masters
    to the granted bodies and their parents instead. Returns None when the
    shared filter is right as it is."""
    granted = _granted_local_bodies(user)
    if granted is None:
        return None
    own_level = next(field for field, column in columns.items() if column == "unique_id")
    return qs.filter(unique_id__in=granted[own_level])


def scoped(qs, scope):
    """Cap `qs` to the requester's data scope and the picked geography."""
    model = qs.model
    if model in STAFF_LINKED_MODELS:
        return qs.filter(staff_id__in=staff_qs(scope).values("staff_unique_id"))
    columns = geo_columns(model)
    if columns is None:
        return qs
    if scope.user is not None:
        capped = (
            _cap_location_master(qs, scope.user, columns) if model in MASTER_GEO_COLUMNS else None
        )
        if capped is not None:
            qs = capped
        else:
            qs = filter_flat_geo_queryset_by_requester_scope(qs, scope.user, field_map=columns)
    if scope.state_ids:
        if "state_id" in columns:
            qs = qs.filter(**{f"{columns['state_id']}__in": scope.state_ids})
        elif "district_id" in columns:
            qs = qs.filter(**{f"{columns['district_id']}__in": District.objects.filter(
                state_id__in=scope.state_ids,
            ).values("unique_id")})
    if scope.district_ids and "district_id" in columns:
        qs = qs.filter(**{f"{columns['district_id']}__in": scope.district_ids})
    if scope.local_bodies:
        picked, applies = Q(), False
        for field, ids in scope.local_bodies:
            if field in columns:
                picked |= Q(**{f"{columns[field]}__in": ids})
                applies = True
        if applies:
            qs = qs.filter(picked)
        elif model in LOCAL_BODY_MODELS:
            # e.g. Municipality master while only corporations are picked.
            qs = qs.none()
    if scope.ward_ids:
        if model is Ward:
            qs = qs.filter(unique_id__in=scope.ward_ids)
        elif has_field(model, "ward_id"):
            qs = qs.filter(ward_id__in=scope.ward_ids)
        elif has_field(model, "ward_ids"):
            qs = qs.filter(json_contains_any("ward_ids", scope.ward_ids))
    return qs


def kg(value):
    return round(float(value or 0), 2)


def pct(part, whole):
    return round(part * 100.0 / whole, 1) if whole else 0.0


def counts_by(qs, field):
    return {
        row[field] or "": row["n"]
        for row in qs.order_by().values(field).annotate(n=Count("pk"))
    }


def local_body_of(row):
    """The local-body id a flat-geo row (or values() dict) belongs to, or ""."""
    get = row.get if isinstance(row, dict) else (lambda f: getattr(row, f, None))
    for field in LOCAL_BODY_FIELDS:
        if get(field):
            return get(field)
    return ""


def per_local_body(qs, *, total=None):
    """{local_body_id: count} — or {local_body_id: sum(total)} when `total`
    is set. Rows outside any local body are keyed ""."""
    agg = Sum(total) if total else Count("pk")
    out = Counter()
    for row in qs.order_by().values(*LOCAL_BODY_FIELDS).annotate(v=agg):
        out[local_body_of(row)] += kg(row["v"]) if total else row["v"]
    return out


def per_column(qs, column, *, total=None):
    """{column value: count} — or sum(total) when `total` is set."""
    agg = Sum(total) if total else Count("pk")
    return {
        row[column] or "": (kg(row["v"]) if total else row["v"])
        for row in qs.order_by().values(column).annotate(v=agg)
    }


def per_district(qs, *, total=None):
    return per_column(qs, "district_id", total=total)


def day_counts(values, scope):
    """Count aware datetimes (or dates) per local day inside the range."""
    out = Counter()
    for value in values:
        if value is None:
            continue
        day = timezone.localtime(value).date() if isinstance(value, datetime) else value
        if scope.start <= day <= scope.end:
            out[day] += 1
    return out


# --------------------------------------------------------- base querysets

def trips_qs(scope):
    return scoped(
        DailyTripAssignment.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    )


def _assignment_ids(scope):
    return trips_qs(scope).values("unique_id")


def trip_logs_qs(scope):
    qs = scoped(
        DailyTripLog.objects.filter(
            is_deleted=False, trip_date__gte=scope.start, trip_date__lte=scope.end,
        ),
        scope,
    )
    # Trip logs carry no ward; a ward pick narrows them through their trip.
    if scope.ward_ids:
        qs = qs.filter(trip_assignment_id__in=_assignment_ids(scope))
    return qs


def breakdowns_qs(scope, *, in_window=True):
    qs = scoped(VehicleBreakdown.objects.filter(is_deleted=False), scope)
    if in_window:
        start_dt, end_dt = scope.window
        qs = qs.filter(created_at__gte=start_dt, created_at__lt=end_dt)
    return qs


def _plan_ids(*collection_types):
    return TripPlan.objects.filter(
        collection_type__in=collection_types, is_deleted=False,
    ).values("unique_id")


def household_waste_qs(scope):
    """Household / bulk weighments — same rule as the dashboard summary: rows
    with no trip, or on a household/bulk trip."""
    assignments = DailyTripAssignment.objects.filter(
        trip_plan_id__in=_plan_ids(
            TripPlan.COLLECTION_TYPE_HOUSEHOLD, TripPlan.COLLECTION_TYPE_BULK,
        ),
        is_deleted=False,
    ).values("unique_id")
    return scoped(
        WasteCollection.objects.filter(
            is_deleted=False,
            collection_date__gte=scope.start,
            collection_date__lte=scope.end,
        ).filter(Q(trip_assignment_id__isnull=True) | Q(trip_assignment_id__in=assignments)),
        scope,
    )


def bin_events_qs(scope):
    return scoped(
        BinCollectionEvent.objects.filter(
            is_deleted=False,
            collection_date__gte=scope.start,
            collection_date__lte=scope.end,
        ),
        scope,
    )


def open_tickets_qs(scope):
    final_ids = ComplaintStatus.objects.filter(is_final=True).values("unique_id")
    return scoped(live(ComplaintTicket.objects.exclude(status_id__in=final_ids)), scope)


def staff_qs(scope):
    return scoped(live(StaffcreationOfficeDetails.objects.all()), scope)


# ---------------------------------------------------------------- masters

# (key, label, group, model). Models without flat geo columns are platform-
# wide reference data and are reported with level "global".
MASTER_CATALOG = (
    ("states", "State", "Location Masters", State),
    ("districts", "District", "Location Masters", District),
    ("area_types", "Area Type", "Location Masters", AreaType),
    ("corporations", "Corporation", "Location Masters", Corporation),
    ("municipalities", "Municipality", "Location Masters", Municipality),
    ("town_panchayats", "Town Panchayat", "Location Masters", TownPanchayat),
    ("panchayat_unions", "Panchayat Union", "Location Masters", PanchayatUnion),
    ("panchayats", "Panchayat", "Location Masters", Panchayat),
    ("wards", "Ward", "Location Masters", Ward),
    ("panchayat_leaders", "Panchayat Leader", "Leader Management", PanchayatLeaderLogin),
    ("district_leaders", "District Leader", "Leader Management", DistrictLeaderLogin),
    ("state_leaders", "State Leader", "Leader Management", StateLeaderLogin),
    ("properties", "Property", "Waste Masters", Property),
    ("subproperties", "Sub Property", "Waste Masters", SubProperty),
    ("bins", "Bin", "Waste Masters", Bins),
    ("waste_types", "Waste Type", "Waste Masters", WasteType),
    ("vehicles", "Vehicle", "Transport Masters", VehicleCreation),
    ("vehicle_types", "Vehicle Type", "Transport Masters", VehicleTypeCreation),
    ("fuels", "Fuel", "Transport Masters", Fuel),
    ("customers", "Customer", "Customer Masters", CustomerCreation),
    ("customer_app_access", "Customer App Access", "Customer Masters", CustomerAccessConfiguration),
    ("staff_templates", "Staff Template", "Schedule Setup", StaffTemplate),
    ("alternative_staff_templates", "Alternative Staff Template", "Schedule Setup", AlternativeStaffTemplate),
    ("collection_points", "Collection Point", "Schedule Setup", Collection_point),
    ("trip_plans", "Trip Plan", "Schedule Setup", TripPlan),
    ("departments", "Department", "Staff Management", Department),
    ("designations", "Designation", "Staff Management", Designation),
    ("staff", "Staff", "Staff Management", StaffcreationOfficeDetails),
    ("staff_data_scopes", "Staff Data Scope", "Staff Management", StaffDataScope),
    ("staff_access_configs", "Staff Access Configuration", "Staff Management", StaffAccessConfiguration),
    ("user_types", "User Type", "Role Management", UserType),
    ("staff_user_types", "Staff User Type", "Role Management", StaffUserType),
    ("government_user_types", "Government User Type", "Role Management", GovernmentStaffUserType),
    ("contractor_user_types", "Contractor User Type", "Role Management", ContractorUserType),
    ("complaint_categories", "Complaint Category", "Complaint Masters", ComplaintCategory),
    ("complaint_subcategories", "Complaint Subcategory", "Complaint Masters", ComplaintSubcategory),
    ("sla_rules", "SLA Rule", "Complaint Masters", ComplaintSlaRule),
)


def master_counts(scope, *, by="local_body"):
    """Every master's total / active / inactive count, plus a breakdown per
    local body (or per district) for the masters that carry geography.

    A location master is keyed by its own id at its own level (each
    Corporation counts towards itself), so the matrix still reads per area."""
    rows = []
    for key, label, group, model in MASTER_CATALOG:
        qs = scoped(live(model.objects.all()), scope)
        total = qs.count()
        active = qs.filter(is_active=True).count() if has_field(model, "is_active") else total
        columns = geo_columns(model) or {}
        breakdown = {}
        if by == "district" and "district_id" in columns:
            breakdown = per_column(qs, columns["district_id"])
        elif by == "local_body" and model in LOCAL_BODY_MODELS:
            breakdown = per_column(qs, "unique_id")
        elif by == "local_body" and all(f in columns for f in LOCAL_BODY_FIELDS):
            breakdown = dict(per_local_body(qs))
        breakdown.pop("", None)
        rows.append({
            "key": key,
            "label": label,
            "group": group,
            "level": "global" if model not in STAFF_LINKED_MODELS and not columns else "geo",
            "total": total,
            "active": active,
            "inactive": max(total - active, 0),
            "breakdown": breakdown,
        })
    return rows


# ------------------------------------------------------------- operations

def operations(scope):
    """Trip, collection, exception and complaint KPIs for the range."""
    plan_types = dict(
        TripPlan.objects.filter(is_deleted=False).values_list("unique_id", "collection_type")
    )

    # ---- trips
    trips = trips_qs(scope)
    trip_status = counts_by(trips, "status")
    trip_approval = counts_by(trips, "approval_status")
    by_type = defaultdict(lambda: {"total": 0, "completed": 0})
    durations = []
    on_time = late = 0
    for plan_id, status, scheduled, started_at, ended_at in trips.values_list(
        "trip_plan_id", "status", "scheduled_time", "actual_start_at", "actual_end_at",
    ):
        ctype = plan_types.get(plan_id) or "unplanned"
        by_type[ctype]["total"] += 1
        if status == DailyTripAssignment.STATUS_COMPLETED:
            by_type[ctype]["completed"] += 1
        if started_at and ended_at and ended_at > started_at:
            durations.append((ended_at - started_at).total_seconds() / 60)
        if started_at and scheduled:
            local_start = timezone.localtime(started_at).time()
            # 15 minutes grace, like the trip delay screen.
            limit = (datetime.combine(date.min, scheduled) + timedelta(minutes=15)).time()
            if local_start <= limit:
                on_time += 1
            else:
                late += 1
    trips_total = sum(trip_status.values())
    completed = trip_status.get(DailyTripAssignment.STATUS_COMPLETED, 0)

    # ---- trip logs
    log_agg = trip_logs_qs(scope).aggregate(
        n=Count("pk"),
        verified=Count("pk", filter=Q(log_status=DailyTripLog.LOG_STATUS_VERIFIED)),
        bin_kg=Sum("collected_weight_kg"),
        household_kg=Sum("household_collected_weight_kg"),
    )

    # ---- household stops and collection points (planned on the trips above)
    assignment_ids = _assignment_ids(scope)
    stop_status = counts_by(
        DailyTripHouseholdCollection.objects.filter(
            is_deleted=False, trip_assignment_id__in=assignment_ids,
        ),
        "status",
    )
    stops_total = sum(stop_status.values())
    stops_collected = stop_status.get(DailyTripHouseholdCollection.STATUS_COLLECTED, 0)
    point_status = counts_by(
        DailyTripCollectionPoint.objects.filter(
            is_deleted=False, trip_assignment_id__in=assignment_ids,
        ),
        "status",
    )
    points_total = sum(point_status.values())
    points_collected = point_status.get(DailyTripCollectionPoint.STATUS_COLLECTED, 0)

    # ---- weighments
    household_agg = household_waste_qs(scope).aggregate(
        n=Count("pk"),
        total=Sum("total_quantity"),
        wet=Sum("wet_waste"),
        dry=Sum("dry_waste"),
        mixed=Sum("mixed_waste"),
        sanitary=Sum("sanitary_waste"),
        customers=Count("customer_id", distinct=True),
    )
    bins = bin_events_qs(scope)
    bin_status = counts_by(bins, "status")
    collected_bins = bins.filter(status=BinCollectionEvent.STATUS_COLLECTED)
    bin_agg = collected_bins.aggregate(
        kg=Sum("collected_weight_kg"), distinct_bins=Count("bin_id", distinct=True),
    )
    household_kg = kg(household_agg["total"])
    bin_kg = kg(bin_agg["kg"])
    total_kg = round(household_kg + bin_kg, 2)

    waste_names = dict(WasteType.objects.values_list("unique_id", "waste_type_name"))
    waste_split = Counter()
    for label, field in (("Wet Waste", "wet"), ("Dry Waste", "dry"),
                         ("Mixed Waste", "mixed"), ("Sanitary Waste", "sanitary")):
        waste_split[label] += kg(household_agg[field])
    classified = sum(waste_split.values())
    if household_kg > classified:
        waste_split["Unclassified"] += round(household_kg - classified, 2)
    for row in collected_bins.order_by().values("waste_type_id").annotate(v=Sum("collected_weight_kg")):
        waste_split[waste_names.get(row["waste_type_id"]) or "Unclassified"] += kg(row["v"])

    # ---- exceptions. Retrip requests have no geography: scope via their trip.
    breakdowns = breakdowns_qs(scope)
    start_dt, end_dt = scope.window
    retrips = TripRetripRequest.objects.filter(
        is_deleted=False, created_at__gte=start_dt, created_at__lt=end_dt,
        assignment_id__in=scoped(
            DailyTripAssignment.objects.filter(is_deleted=False), scope,
        ).values("unique_id"),
    )

    days = max(len(scope.days), 1)
    return {
        "trips": {
            "total": trips_total,
            "completed": completed,
            "in_progress": trip_status.get(DailyTripAssignment.STATUS_IN_PROGRESS, 0),
            "scheduled": trip_status.get(DailyTripAssignment.STATUS_SCHEDULED, 0),
            "cancelled": trip_status.get(DailyTripAssignment.STATUS_CANCELLED, 0),
            "completion_rate": pct(completed, trips_total),
            "approval": trip_approval,
            "by_collection_type": dict(by_type),
            "vehicles_used": trips.exclude(vehicle_id__isnull=True).values("vehicle_id").distinct().count(),
            "teams_used": trips.exclude(staff_template_id__isnull=True).values("staff_template_id").distinct().count(),
            "avg_duration_min": round(sum(durations) / len(durations), 1) if durations else 0,
            "on_time": on_time,
            "late_start": late,
            "on_time_rate": pct(on_time, on_time + late),
            "per_day": round(trips_total / days, 1),
        },
        "trip_logs": {
            "total": log_agg["n"] or 0,
            "verified": log_agg["verified"] or 0,
            "unverified": max((log_agg["n"] or 0) - (log_agg["verified"] or 0), 0),
            "verification_rate": pct(log_agg["verified"] or 0, log_agg["n"] or 0),
            "bin_kg": kg(log_agg["bin_kg"]),
            "household_kg": kg(log_agg["household_kg"]),
            "total_kg": round(kg(log_agg["bin_kg"]) + kg(log_agg["household_kg"]), 2),
        },
        "waste": {
            "total_kg": total_kg,
            "total_tons": round(total_kg / 1000, 2),
            "household_kg": household_kg,
            "bin_kg": bin_kg,
            "avg_kg_per_day": round(total_kg / days, 2),
            "avg_kg_per_trip": round(total_kg / completed, 2) if completed else 0,
            "by_waste_type": [
                {"name": name, "kg": round(value, 2), "share": pct(value, total_kg)}
                for name, value in waste_split.most_common()
                if value > 0
            ],
        },
        "households": {
            "weighments": household_agg["n"] or 0,
            "customers_served": household_agg["customers"] or 0,
            "planned_stops": stops_total,
            "collected": stops_collected,
            "status": stop_status,
            "coverage_rate": pct(stops_collected, stops_total),
        },
        "bins": {
            "events": sum(bin_status.values()),
            "collected": bin_status.get(BinCollectionEvent.STATUS_COLLECTED, 0),
            "distinct_bins_collected": bin_agg["distinct_bins"] or 0,
            "status": bin_status,
        },
        "collection_points": {
            "planned": points_total,
            "status": point_status,
            "collected": points_collected,
            "coverage_rate": pct(points_collected, points_total),
        },
        # The government build has no trip-delay reports, so only breakdowns
        # and retrips are reported here.
        "exceptions": {
            "breakdowns": breakdowns.count(),
            "breakdown_status": counts_by(breakdowns, "status"),
            "breakdown_reasons": counts_by(breakdowns, "breakdown_reason"),
            "retrips": retrips.count(),
            "retrip_status": counts_by(retrips, "status"),
        },
        "complaints": complaint_tickets(scope),
        "attendance": attendance_summary(scope),
    }


def complaint_tickets(scope):
    start_dt, end_dt = scope.window
    final_ids = set(
        ComplaintStatus.objects.filter(is_final=True).values_list("unique_id", flat=True)
    )
    status_names = dict(ComplaintStatus.objects.values_list("unique_id", "status_name"))
    all_tickets = scoped(live(ComplaintTicket.objects.all()), scope)
    raised = all_tickets.filter(created__gte=start_dt, created__lt=end_dt)
    open_now = all_tickets.exclude(status_id__in=final_ids)
    now = timezone.now()
    return {
        "raised": raised.count(),
        "resolved": all_tickets.filter(resolved_at__gte=start_dt, resolved_at__lt=end_dt).count(),
        "closed": all_tickets.filter(closed_at__gte=start_dt, closed_at__lt=end_dt).count(),
        "open": open_now.count(),
        "escalated_open": open_now.filter(is_escalated=True).count(),
        "overdue_open": open_now.filter(next_escalation_due_at__lt=now).count(),
        "reopened": raised.filter(reopened_count__gt=0).count(),
        "by_status": {
            status_names.get(key, key or "Unknown"): value
            for key, value in counts_by(raised, "status_id").items()
        },
    }


def attendance_summary(scope):
    """Distinct staff punched IN per day (face recognition). The punch log
    has no geography, so it is scoped through the scoped staff list."""
    staff = staff_qs(scope).filter(active_status=True)
    present = defaultdict(set)
    for staff_id, day in DailyAttendanceReg.objects.filter(
        staff_id__in=staff.values("staff_unique_id"), punch_type="IN",
        recognition_date__gte=scope.start, recognition_date__lte=scope.end,
    ).values_list("staff_id", "recognition_date"):
        present[day].add(staff_id)
    total = staff.count()
    per_day_counts = {day: len(ids) for day, ids in present.items()}
    days = max(len(scope.days), 1)
    avg = round(sum(per_day_counts.values()) / days, 1)
    return {
        "staff": total,
        "avg_present": avg,
        "attendance_rate": pct(avg, total),
        "present_last_day": per_day_counts.get(scope.end, 0),
        # JSON object keys must be strings.
        "per_day": {day.isoformat(): count for day, count in per_day_counts.items()},
    }


# ------------------------------------------------------------------ daily

def daily_series(scope):
    """One row per day of the range: trips, weights, stops, exceptions."""
    rows = {
        day: {
            "date": day.isoformat(),
            "trips": 0, "trips_completed": 0, "trip_logs": 0,
            "household_kg": 0.0, "bin_kg": 0.0, "total_kg": 0.0,
            "households_collected": 0, "bins_collected": 0,
            "breakdowns": 0, "complaints": 0, "present": 0,
        }
        for day in scope.days
    }

    for row in trips_qs(scope).order_by().values("trip_date").annotate(
        n=Count("pk"),
        done=Count("pk", filter=Q(status=DailyTripAssignment.STATUS_COMPLETED)),
    ):
        if row["trip_date"] in rows:
            rows[row["trip_date"]]["trips"] = row["n"]
            rows[row["trip_date"]]["trips_completed"] = row["done"]

    for row in trip_logs_qs(scope).order_by().values("trip_date").annotate(n=Count("pk")):
        if row["trip_date"] in rows:
            rows[row["trip_date"]]["trip_logs"] = row["n"]

    for row in household_waste_qs(scope).order_by().values("collection_date").annotate(
        v=Sum("total_quantity"), n=Count("customer_id", distinct=True),
    ):
        if row["collection_date"] in rows:
            rows[row["collection_date"]]["household_kg"] = kg(row["v"])
            rows[row["collection_date"]]["households_collected"] = row["n"]

    collected = bin_events_qs(scope).filter(status=BinCollectionEvent.STATUS_COLLECTED)
    for row in collected.order_by().values("collection_date").annotate(
        v=Sum("collected_weight_kg"), n=Count("bin_id", distinct=True),
    ):
        if row["collection_date"] in rows:
            rows[row["collection_date"]]["bin_kg"] = kg(row["v"])
            rows[row["collection_date"]]["bins_collected"] = row["n"]

    start_dt, end_dt = scope.window
    breakdown_days = day_counts(breakdowns_qs(scope).values_list("created_at", flat=True), scope)
    ticket_days = day_counts(
        scoped(
            live(ComplaintTicket.objects.filter(created__gte=start_dt, created__lt=end_dt)),
            scope,
        ).values_list("created", flat=True),
        scope,
    )
    present = attendance_summary(scope)["per_day"]
    for day, row in rows.items():
        row["total_kg"] = round(row["household_kg"] + row["bin_kg"], 2)
        row["breakdowns"] = breakdown_days.get(day, 0)
        row["complaints"] = ticket_days.get(day, 0)
        row["present"] = present.get(day.isoformat(), 0)
    return list(rows.values())


# ---------------------------------------------------------------- leaders

def local_body_names(ids=None):
    """{local_body_id: (name, level label)} across all five levels."""
    out = {}
    for _field, model, name_field, label in LOCAL_BODY_LEVELS:
        qs = model.objects.all()
        if ids is not None:
            qs = qs.filter(unique_id__in=ids)
        for uid, name in qs.values_list("unique_id", name_field):
            out[uid] = (name or uid, label)
    return out


def top_performers(scope, limit=10):
    """Top vehicles, drivers, local bodies and wards by collected weight."""
    logs = trip_logs_qs(scope)

    def ranked(field):
        totals = defaultdict(lambda: {"trips": 0, "kg": Decimal("0")})
        for key, bin_kg, household_kg in logs.exclude(**{f"{field}__isnull": True}).values_list(
            field, "collected_weight_kg", "household_collected_weight_kg",
        ):
            totals[key]["trips"] += 1
            totals[key]["kg"] += Decimal(str(bin_kg or 0)) + Decimal(str(household_kg or 0))
        return sorted(totals.items(), key=lambda item: item[1]["kg"], reverse=True)[:limit]

    vehicles = ranked("vehicle_id")
    vehicle_names = dict(
        VehicleCreation.objects.filter(unique_id__in=[k for k, _ in vehicles])
        .values_list("unique_id", "vehicle_no")
    )
    drivers = ranked("driver_id")
    driver_names = dict(
        StaffcreationOfficeDetails.objects.filter(staff_unique_id__in=[k for k, _ in drivers])
        .values_list("staff_unique_id", "employee_name")
    )

    # Local bodies: household + bin weight, both carry the local-body columns.
    body_kg = per_local_body(household_waste_qs(scope), total="total_quantity")
    body_kg.update(per_local_body(
        bin_events_qs(scope).filter(status=BinCollectionEvent.STATUS_COLLECTED),
        total="collected_weight_kg",
    ))
    body_trips = per_local_body(trip_logs_qs(scope))
    body_kg.pop("", None)
    top_bodies = body_kg.most_common(limit)
    body_names = local_body_names([k for k, _ in top_bodies])

    wards = (
        household_waste_qs(scope).exclude(ward_id__isnull=True)
        .order_by().values("ward_id")
        .annotate(v=Sum("total_quantity"), n=Count("pk"))
        .order_by("-v")[:limit]
    )
    ward_names = dict(
        Ward.objects.filter(unique_id__in=[r["ward_id"] for r in wards])
        .values_list("unique_id", "ward_name")
    )
    return {
        "vehicles": [
            {"id": key, "name": vehicle_names.get(key, key), "trips": v["trips"], "kg": kg(v["kg"])}
            for key, v in vehicles
        ],
        "drivers": [
            {"id": key, "name": driver_names.get(key, key), "trips": v["trips"], "kg": kg(v["kg"])}
            for key, v in drivers
        ],
        "local_bodies": [
            {"id": key, "name": body_names.get(key, (key, ""))[0],
             "type_label": body_names.get(key, (key, ""))[1],
             "trips": body_trips.get(key, 0), "kg": kg(value)}
            for key, value in top_bodies
        ],
        "wards": [
            {"id": r["ward_id"], "name": ward_names.get(r["ward_id"], r["ward_id"]),
             "collections": r["n"], "kg": kg(r["v"])}
            for r in wards
        ],
    }


# ------------------------------------------------------- per area breakdown

def area_breakdown(scope, *, by="local_body"):
    """Operations + headcount per local body (or per district), keyed by its
    id, for the comparison tables. Rows outside any area are keyed ""."""
    group = per_local_body if by == "local_body" else per_district
    trips = trips_qs(scope)
    trip_counts = group(trips)
    trips_done = group(trips.filter(status=DailyTripAssignment.STATUS_COMPLETED))
    household_kg = group(household_waste_qs(scope), total="total_quantity")
    collected_bins = bin_events_qs(scope).filter(status=BinCollectionEvent.STATUS_COLLECTED)
    bin_kg = group(collected_bins, total="collected_weight_kg")
    metrics = {
        "trips": trip_counts,
        "trips_completed": trips_done,
        "trip_logs": group(trip_logs_qs(scope)),
        "household_kg": household_kg,
        "bin_kg": bin_kg,
        "bins_collected": group(collected_bins),
        "breakdowns": group(breakdowns_qs(scope)),
        "open_complaints": group(open_tickets_qs(scope)),
        "staff": group(staff_qs(scope)),
        "vehicles": group(scoped(live(VehicleCreation.objects.all()), scope)),
        "customers": group(scoped(live(CustomerCreation.objects.all()), scope)),
        "bins": group(scoped(live(Bins.objects.all()), scope)),
    }
    keys = set()
    for values in metrics.values():
        keys |= set(values)
    out = {}
    for key in keys:
        row = {name: values.get(key, 0) for name, values in metrics.items()}
        row["total_kg"] = round(row["household_kg"] + row["bin_kg"], 2)
        row["completion_rate"] = pct(row["trips_completed"], row["trips"])
        out[key] = row
    return out


EMPTY_AREA_ROW = {
    "trips": 0, "trips_completed": 0, "completion_rate": 0.0, "trip_logs": 0,
    "household_kg": 0.0, "bin_kg": 0.0, "total_kg": 0.0, "bins_collected": 0,
    "breakdowns": 0, "open_complaints": 0, "staff": 0, "vehicles": 0,
    "customers": 0, "bins": 0,
}


def fleet_health(scope):
    """Vehicle master health: active, idle on the last day, insurance due."""
    vehicles = scoped(live(VehicleCreation.objects.all()), scope)
    today = timezone.localdate()
    used_last_day = set(
        scoped(
            DailyTripAssignment.objects.filter(is_deleted=False, trip_date=scope.end),
            scope,
        ).exclude(vehicle_id__isnull=True).values_list("vehicle_id", flat=True)
    )
    active_ids = set(vehicles.filter(is_active=True).values_list("unique_id", flat=True))
    insurance = vehicles.exclude(insurance_expiry_date__isnull=True)
    return {
        "total": vehicles.count(),
        "active": len(active_ids),
        "on_trip_last_day": len(active_ids & used_last_day),
        "idle_last_day": len(active_ids - used_last_day),
        "insurance_expired": insurance.filter(insurance_expiry_date__lt=today).count(),
        "insurance_due_30d": insurance.filter(
            insurance_expiry_date__gte=today,
            insurance_expiry_date__lte=today + timedelta(days=30),
        ).count(),
        "open_breakdowns": breakdowns_qs(scope, in_window=False).filter(
            status=VehicleBreakdown.STATUS_REPORTED,
        ).count(),
    }


def role_names():
    """{role type id: display name} across government, staff and contractor
    role masters."""
    names = {}
    for model in (ContractorUserType, StaffUserType, GovernmentStaffUserType):
        names.update(model.objects.values_list("unique_id", "name"))
    return names


def staff_role(row, names):
    """Display role of a staff values() row (government role first)."""
    for field in ("governmentusertype_id", "staffusertype_id", "contractorusertype_id"):
        if row.get(field) and names.get(row[field]):
            return pretty_name(names[row[field]])
    return "Unassigned"


def staff_summary(scope):
    staff = staff_qs(scope)
    agg = staff.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True, active_status=True)),
        login_enabled=Count("pk", filter=Q(login_enabled=True)),
    )
    names = role_names()
    roles = Counter(
        staff_role(row, names)
        for row in staff.values("governmentusertype_id", "staffusertype_id", "contractorusertype_id")
    )
    return {**{k: v or 0 for k, v in agg.items()}, "by_role": dict(roles.most_common())}


def pretty_name(name):
    """"govt_corporation_admin" -> "Corporation Admin"."""
    if not name:
        return "Unassigned"
    text = str(name)
    if text.startswith("govt_"):
        text = text[len("govt_"):]
    return text.replace("_", " ").title()
