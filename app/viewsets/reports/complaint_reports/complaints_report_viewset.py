"""Complaints report: intake, resolution, pendency and escalation analytics
over ComplaintTicket for one received-date range.

Every aggregate is computed from the same filtered ticket set (requester
scope + date range + location/category/source), so the KPIs, charts, area
table and register always agree with each other. The register's status tab
and search only narrow the register rows, never the aggregates above them.

The ticket's master references (status/category/source/geo/staff) are plain
CharFields holding the master's unique_id, so names are resolved with one
lookup per master rather than ORM joins.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.response import Response

from app.models.core_modules.complaint_management import (
    ComplaintCategory,
    ComplaintSource,
    ComplaintStatus,
    ComplaintTicket,
)
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.serializers.core_modules.complaint_management.transaction_serializers import ComplaintTicketSerializer
from app.services.complaint_escalation import CLOSED_STATUS_CODES
from app.viewsets.core_modules.complaint_management.ticket_viewset import (
    _area_type_q,
    _local_body_q,
    scope_tickets_to_requester,
)

# CLOSED_STATUS_CODES also covers REJECTED/CANCELLED; those are closed but
# not "resolved", so they get their own bucket and stay out of SLA figures.
RESOLVED_STATUS_CODES = ("RESOLVED", "CLOSED")
STATUS_BUCKETS = ("open", "in_progress", "escalated", "resolved")
DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 366
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100
AGE_BUCKETS = (
    ("0_24", "0 – 24 h", 0, 24),
    ("24_48", "24 – 48 h", 24, 48),
    ("48_72", "48 – 72 h", 48, 72),
    ("72_plus", "Over 72 h", 72, None),
)
# (ticket column, master, name attribute, label)
LOCAL_BODIES = (
    ("corporation_id", Corporation, "corporation_name", "Corporation"),
    ("municipality_id", Municipality, "municipality_name", "Municipality"),
    ("town_panchayat_id", TownPanchayat, "town_panchayat_name", "Town Panchayat"),
    ("panchayat_union_id", PanchayatUnion, "union_name", "Panchayat Union"),
    ("panchayat_id", Panchayat, "panchayat_name", "Panchayat"),
)
TICKET_FIELDS = (
    "unique_id",
    "ticket_no",
    "created",
    "category_id",
    "source_id",
    "status_id",
    "district_id",
    *(field for field, *_ in LOCAL_BODIES),
    "assigned_staff_id",
    "escalated_to_staff_id",
    "is_escalated",
    "escalation_level",
    "next_escalation_due_at",
    "resolved_at",
    "closed_at",
)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _start_of_day(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _positive_int(value, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _percent(part, whole):
    return round(part * 100 / whole, 1) if whole else 0.0


def _comma_values(value):
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _status_bucket(status_code, is_escalated):
    if status_code in RESOLVED_STATUS_CODES:
        return "resolved"
    if status_code in CLOSED_STATUS_CODES:
        return "rejected"
    if is_escalated or status_code == "ESCALATED":
        return "escalated"
    if status_code == "IN_PROGRESS":
        return "in_progress"
    return "open"


def _finished_at(row):
    return row["resolved_at"] or row["closed_at"]


def _is_breached(row, bucket, now):
    """A ticket misses SLA once it has escalated past its first level, or
    once its current level's deadline passed while it is still open."""
    if row["is_escalated"]:
        return True
    due = row["next_escalation_due_at"]
    return bool(due and bucket not in ("resolved", "rejected") and now > due)


def _local_body(row):
    """(column, unique_id) of the ticket's local body, or (None, None)."""
    for field, *_ in LOCAL_BODIES:
        if row.get(field):
            return field, row[field]
    return None, None


def _name_map(model, key_field, name_field, ids):
    ids = {value for value in ids if value}
    if not ids:
        return {}
    return dict(model.objects.filter(**{f"{key_field}__in": ids}).values_list(key_field, name_field))


class ComplaintsReportViewSet(viewsets.ViewSet):
    permission_resource = "ComplaintsReport"
    serializer_class = ComplaintTicketSerializer

    def _date_range(self, params):
        today = timezone.localdate()
        to_date = _parse_date(params.get("to_date")) or today
        from_date = _parse_date(params.get("from_date")) or (to_date - timedelta(days=DEFAULT_RANGE_DAYS - 1))
        if from_date > to_date:
            from_date, to_date = to_date, from_date
        if (to_date - from_date).days >= MAX_RANGE_DAYS:
            from_date = to_date - timedelta(days=MAX_RANGE_DAYS - 1)
        return from_date, to_date

    def list(self, request):
        params = request.query_params
        now = timezone.now()
        from_date, to_date = self._date_range(params)

        scoped = scope_tickets_to_requester(ComplaintTicket.objects.filter(is_deleted=False), request.user)
        option_rows = list(scoped.values("category_id", "source_id").distinct())

        # Aware day bounds instead of `created__date__*`: on MySQL without
        # loaded timezone tables CONVERT_TZ yields NULL and matches nothing.
        queryset = scoped.filter(
            created__gte=_start_of_day(from_date),
            created__lt=_start_of_day(to_date + timedelta(days=1)),
        )
        if params.get("state"):
            queryset = queryset.filter(state_id=params["state"])
        if params.get("district"):
            queryset = queryset.filter(district_id=params["district"])
        if params.get("area_type"):
            queryset = queryset.filter(_area_type_q(params["area_type"]))
        if params.get("city"):
            queryset = queryset.filter(_local_body_q(params["city"]))
        for param in ("category_id", "source_id"):
            values = _comma_values(params.get(param))
            if values:
                queryset = queryset.filter(**{f"{param}__in": values})

        rows = list(queryset.order_by("-created").values(*TICKET_FIELDS))

        statuses = {
            unique_id: (code, name)
            for unique_id, code, name in ComplaintStatus.objects.filter(
                unique_id__in={r["status_id"] for r in rows if r["status_id"]}
            ).values_list("unique_id", "status_code", "status_name")
        }
        categories = _name_map(
            ComplaintCategory, "unique_id", "category_name",
            [r["category_id"] for r in rows] + [r["category_id"] for r in option_rows],
        )
        sources = _name_map(
            ComplaintSource, "unique_id", "source_name",
            [r["source_id"] for r in rows] + [r["source_id"] for r in option_rows],
        )
        districts = _name_map(District, "unique_id", "name", [r["district_id"] for r in rows])
        local_bodies = {}
        for field, model, name_attr, _label in LOCAL_BODIES:
            local_bodies[field] = _name_map(model, "unique_id", name_attr, [r[field] for r in rows])
        staff = _name_map(
            StaffcreationOfficeDetails, "staff_unique_id", "employee_name",
            [r["assigned_staff_id"] for r in rows] + [r["escalated_to_staff_id"] for r in rows],
        )
        local_body_labels = {field: label for field, _model, _attr, label in LOCAL_BODIES}

        bucket_counts = defaultdict(int)
        received_by_day = defaultdict(int)
        resolved_by_day = defaultdict(int)
        category_counts = defaultdict(int)
        age_counts = defaultdict(int)
        area_stats = defaultdict(lambda: {"received": 0, "resolved": 0, "pending": 0, "escalated": 0, "sla_total": 0, "sla_met": 0})
        sla_total = sla_met = 0
        resolution_hours = []

        for row in rows:
            status_code, status_name = statuses.get(row["status_id"], ("", ""))
            bucket = _status_bucket(status_code, row["is_escalated"])
            breached = _is_breached(row, bucket, now)
            finished = _finished_at(row) if bucket == "resolved" else None
            lb_field, lb_id = _local_body(row)

            row["_bucket"] = bucket
            row["_status_code"] = status_code
            row["_status_name"] = status_name
            row["_breached"] = breached
            row["_local_body"] = (lb_field, lb_id)
            row["_resolution_hours"] = (
                round((finished - row["created"]).total_seconds() / 3600, 1) if finished else None
            )

            bucket_counts[bucket] += 1
            received_by_day[timezone.localtime(row["created"]).date()] += 1
            category_counts[row["category_id"]] += 1

            area = area_stats[(row["district_id"], lb_field, lb_id)]
            area["received"] += 1
            if row["is_escalated"]:
                area["escalated"] += 1

            if bucket == "resolved":
                area["resolved"] += 1
                if finished:
                    resolved_by_day[timezone.localtime(finished).date()] += 1
                    resolution_hours.append(row["_resolution_hours"])
            elif bucket != "rejected":
                area["pending"] += 1
                age_hours = (now - row["created"]).total_seconds() / 3600
                for key, _label, low, high in AGE_BUCKETS:
                    if age_hours >= low and (high is None or age_hours < high):
                        age_counts[key] += 1
                        break

            if bucket != "rejected":
                sla_total += 1
                area["sla_total"] += 1
                if not breached:
                    sla_met += 1
                    area["sla_met"] += 1

        total = len(rows)
        pending_total = sum(age_counts.values())

        daily_trend = []
        day = from_date
        while day <= to_date:
            daily_trend.append({
                "date": day.isoformat(),
                "received": received_by_day.get(day, 0),
                "resolved": resolved_by_day.get(day, 0),
            })
            day += timedelta(days=1)

        category_breakdown = sorted(
            (
                {
                    "category_id": category_id or "",
                    "category_name": categories.get(category_id) or "Uncategorised",
                    "count": count,
                    "share_percent": _percent(count, total),
                }
                for category_id, count in category_counts.items()
            ),
            key=lambda item: -item["count"],
        )

        area_breakdown = sorted(
            (
                {
                    "district_id": district_id or "",
                    "district_name": districts.get(district_id) or "",
                    "local_body_id": lb_id or "",
                    "local_body_name": local_bodies.get(lb_field, {}).get(lb_id) or "",
                    "local_body_type": local_body_labels.get(lb_field, ""),
                    "received": stats["received"],
                    "resolved": stats["resolved"],
                    "pending": stats["pending"],
                    "escalated": stats["escalated"],
                    "sla_compliance_percent": _percent(stats["sla_met"], stats["sla_total"]),
                }
                for (district_id, lb_field, lb_id), stats in area_stats.items()
            ),
            key=lambda item: (-item["pending"], -item["received"]),
        )

        # Register: status tab + search narrow the rows, not the aggregates.
        register = rows
        status_filter = (params.get("status") or "").strip().lower()
        if status_filter in STATUS_BUCKETS:
            register = [r for r in register if r["_bucket"] == status_filter]
        search = (params.get("search") or "").strip().lower()
        if search:
            register = [r for r in register if search in (r["ticket_no"] or "").lower()]

        count = len(register)
        if params.get("export") in ("1", "true", "True"):
            page_rows = register
        else:
            limit = min(_positive_int(params.get("limit"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
            page = _positive_int(params.get("page"), 1)
            page_rows = register[(page - 1) * limit: page * limit]

        results = []
        for r in page_rows:
            lb_field, lb_id = r["_local_body"]
            owner_id = r["escalated_to_staff_id"] or r["assigned_staff_id"]
            results.append({
                "unique_id": r["unique_id"],
                "ticket_no": r["ticket_no"],
                "created": r["created"],
                "category_name": categories.get(r["category_id"]) or "",
                "district_name": districts.get(r["district_id"]) or "",
                "local_body_name": local_bodies.get(lb_field, {}).get(lb_id) or "",
                "local_body_type": local_body_labels.get(lb_field, ""),
                "source_name": sources.get(r["source_id"]) or "",
                "assigned_staff_name": staff.get(owner_id) or "",
                "escalation_level": r["escalation_level"] or None,
                "status_code": r["_status_code"],
                "status_name": r["_status_name"],
                "status_bucket": r["_bucket"],
                "next_escalation_due_at": r["next_escalation_due_at"],
                "resolved_at": _finished_at(r) if r["_bucket"] == "resolved" else None,
                "resolution_hours": r["_resolution_hours"],
                "is_breached": r["_breached"],
            })

        return Response({
            "period": {"from_date": from_date.isoformat(), "to_date": to_date.isoformat()},
            "kpis": {
                "total": total,
                "open": bucket_counts["open"],
                "in_progress": bucket_counts["in_progress"],
                "escalated": bucket_counts["escalated"],
                "resolved": bucket_counts["resolved"],
                "rejected": bucket_counts["rejected"],
                "pending": pending_total,
                "resolved_percent": _percent(bucket_counts["resolved"], total),
                "sla_compliance_percent": _percent(sla_met, sla_total),
                "avg_resolution_hours": (
                    round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None
                ),
                "district_count": len({r["district_id"] for r in rows if r["district_id"]}),
                "local_body_count": len({r["_local_body"] for r in rows if r["_local_body"][1]}),
            },
            "status_counts": {"all": total, **{bucket: bucket_counts[bucket] for bucket in STATUS_BUCKETS}},
            "daily_trend": daily_trend,
            "category_breakdown": category_breakdown,
            "pending_aging": [
                {"key": key, "label": label, "count": age_counts[key]}
                for key, label, _low, _high in AGE_BUCKETS
            ],
            "area_breakdown": area_breakdown,
            "filter_options": {
                "categories": sorted(
                    (
                        {"value": cid, "label": categories[cid]}
                        for cid in {r["category_id"] for r in option_rows}
                        if cid in categories
                    ),
                    key=lambda item: item["label"].lower(),
                ),
                "sources": sorted(
                    (
                        {"value": sid, "label": sources[sid]}
                        for sid in {r["source_id"] for r in option_rows}
                        if sid in sources
                    ),
                    key=lambda item: item["label"].lower(),
                ),
            },
            "results": results,
            "count": count,
        })
