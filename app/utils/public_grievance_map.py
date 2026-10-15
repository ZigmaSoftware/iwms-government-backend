"""
Payloads for the public grievance map (no login), in three drill-down steps:

  state       every district of the state with its complaint counts — the
              frontend draws district shapes from its bundled GeoJSON
  district    that district plus each ULB / RLB in it with its geofence
              (master `coordinates`) and complaint counts
  local body  one ULB / RLB: its geofence, complaint counts by status, the
              Staff Hierarchy escalation chain that handles its complaints
              (with the officer currently covering each level and how many
              open complaints sit there) and the complaint pins

Complaint counts cover every non-deleted ticket; pins leave out tickets
flagged `is_sensitive` and never carry reporter details. A pin carries the
complaint's photos (image attachments not flagged `is_sensitive`) and, while
one waits for the officer's check, the citizen's cleanup photo.

Two anonymous actions hang off a pin: "I saw this too" (`mark_seen`) and
"Verify Cleanup" (app/services/complaint_cleanup.py) — approving that closes
the ticket.
"""
from datetime import timedelta

from django.db.models import Count, F, Q
from django.utils import timezone

from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.cleanup_report import ComplaintCleanupReport
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.subcategory_master import ComplaintSubcategory
from app.models.core_modules.complaint_management.ticket_attachment import ComplaintAttachment
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.masters.district import District
from app.models.superadmin.common_masters.state import State
from app.services.complaint_escalation import (
    CLOSED_STATUS_CODES,
    hierarchy_level_options,
    staff_for_level,
)
from app.services.complaint_cleanup import CLEANUP_PROOF
from app.utils.leader_map import LOCAL_BODY_TYPES, _clean_coordinates
from app.utils.staff_hierarchy import complete_geo

RESOLVED_STATUS_CODES = ("RESOLVED", "CLOSED")
# most recent first; a body with more open/recent tickets than this shows the newest
MAX_PINS = 500

CLEANUP_MAX_BYTES = 8 * 1024 * 1024
CLEANUP_NOTE_MAX = 500

LOCAL_BODY_BY_TYPE = {entry[0]: entry for entry in LOCAL_BODY_TYPES}

EMPTY = {"total": 0, "open": 0, "resolved": 0, "escalated": 0}


def default_state():
    """Tamil Nadu when present, else the first active state."""
    states = State.objects.filter(is_deleted=False, is_active=True)
    return (
        states.filter(name__iexact="Tamil Nadu").first()
        or states.filter(name__icontains="tamil").first()
        or states.order_by("name").first()
    )


def _status_ids():
    rows = list(ComplaintStatus.objects.filter(is_deleted=False).values_list("unique_id", "status_code"))
    closed = [uid for uid, code in rows if code in CLOSED_STATUS_CODES]
    resolved = [uid for uid, code in rows if code in RESOLVED_STATUS_CODES]
    return closed, resolved


def _count_annotations(closed, resolved):
    is_open = ~Q(status_id__in=closed)
    return {
        "total": Count("unique_id"),
        "open": Count("unique_id", filter=is_open),
        "resolved": Count("unique_id", filter=Q(status_id__in=resolved)),
        "escalated": Count("unique_id", filter=is_open & Q(is_escalated=True)),
    }


def _counts_by(qs, column, annotations):
    rows = qs.exclude(**{f"{column}__isnull": True}).exclude(**{column: ""}).values(column).annotate(**annotations)
    return {r[column]: {k: r[k] for k in EMPTY} for r in rows}


def _by_status(qs):
    statuses = {
        s.unique_id: s
        for s in ComplaintStatus.objects.filter(is_deleted=False)
    }
    rows = qs.values("status_id").annotate(n=Count("unique_id"))
    out = []
    for r in rows:
        s = statuses.get(r["status_id"])
        out.append({
            "code": s.status_code if s else None,
            "name": s.status_name if s else "Unknown",
            "is_final": bool(s and s.is_final),
            "count": r["n"],
        })
    return sorted(out, key=lambda x: -x["count"])


def _by_level(open_qs):
    """Open complaints per escalation level (0 = not yet on the chain)."""
    rows = open_qs.values("escalation_level").annotate(n=Count("unique_id"))
    return {r["escalation_level"] or 0: r["n"] for r in rows}


def _tickets(state_id):
    return ComplaintTicket.objects.filter(is_deleted=False, state_id=state_id)


def build_state(state):
    closed, resolved = _status_ids()
    tickets = _tickets(state.unique_id)
    ann = _count_annotations(closed, resolved)
    counts = _counts_by(tickets, "district_id", ann)
    districts = [
        {"district_id": d.unique_id, "name": d.name, **counts.get(d.unique_id, EMPTY)}
        for d in District.objects.filter(state_id=state.unique_id, is_deleted=False, is_active=True).order_by("name")
    ]
    open_qs = tickets.exclude(status_id__in=closed)
    return {
        "scope": "state",
        "state_id": state.unique_id,
        "state_name": state.name,
        "districts": districts,
        "totals": tickets.aggregate(**ann),
        "by_status": _by_status(tickets),
        "by_level": _by_level(open_qs),
    }


def build_district(district):
    closed, resolved = _status_ids()
    state = State.objects.filter(unique_id=district.state_id).first()
    tickets = _tickets(district.state_id).filter(district_id=district.unique_id)
    ann = _count_annotations(closed, resolved)
    local_bodies = []
    for type_key, category, model, name_field, column in LOCAL_BODY_TYPES:
        counts = _counts_by(tickets, column, ann)
        for obj in model.objects.filter(district_id=district.unique_id, is_deleted=False, is_active=True).order_by(name_field):
            local_bodies.append({
                "id": obj.unique_id,
                "type": type_key,
                "category": category,
                "name": getattr(obj, name_field),
                "coordinates": _clean_coordinates(obj.coordinates),
                **counts.get(obj.unique_id, EMPTY),
            })
    return {
        "scope": "district",
        "state_id": district.state_id,
        "state_name": state.name if state else "",
        "district_id": district.unique_id,
        "district_name": district.name,
        "district_coordinates": _clean_coordinates(district.coordinates),
        "local_bodies": local_bodies,
        "totals": tickets.aggregate(**ann),
        "by_status": _by_status(tickets),
        "by_level": _by_level(tickets.exclude(status_id__in=closed)),
    }


def find_local_body(type_key, unique_id):
    entry = LOCAL_BODY_BY_TYPE.get(type_key)
    if not entry or not unique_id:
        return None, None
    obj = entry[2].objects.filter(unique_id=unique_id, is_deleted=False).first()
    return (entry, obj) if obj else (None, None)


def _hierarchy(geo, open_by_level):
    """The escalation chain for an area, lowest level first: the roles at
    each level, the staff member who would receive a complaint there, and
    the open complaints currently sitting at that level."""
    options = hierarchy_level_options(geo)
    levels = {role["unique_id"]: opt["level"] for opt in options for role in opt["roles"]}
    full_geo = complete_geo(geo)
    chain = []
    for opt in options:
        staff = staff_for_level(opt["level"], full_geo, levels)
        chain.append({
            "level": opt["level"],
            "roles": [role["name"] for role in opt["roles"]],
            # name + designation only — no contact details on a public page
            "officer": (
                {"name": staff.employee_name, "designation": staff.designation or ""}
                if staff else None
            ),
            "open": open_by_level.get(opt["level"], 0),
        })
    return chain


def _photos(ticket_ids, request=None):
    """({ticket_id: [complaint photo url, ...]} oldest first,
    {ticket_id: pending cleanup photo url})."""
    absolute = (lambda url: request.build_absolute_uri(url)) if request else (lambda url: url)
    photos = {}
    rows = ComplaintAttachment.objects.filter(
        ticket_id__in=ticket_ids, is_deleted=False, is_sensitive=False,
    ).filter(Q(mime_type__startswith="image/") | Q(file_type="photo")).exclude(file_type=CLEANUP_PROOF).order_by("created")
    for attachment in rows:
        if attachment.file:
            photos.setdefault(attachment.ticket_id, []).append(absolute(attachment.file.url))

    pending = dict(
        ComplaintCleanupReport.objects.filter(
            ticket_id__in=ticket_ids, status=ComplaintCleanupReport.STATUS_PENDING, is_deleted=False,
        ).values_list("ticket_id", "attachment_id")
    )
    files = {
        a.unique_id: a.file
        for a in ComplaintAttachment.objects.filter(unique_id__in=pending.values())
        if a.file
    }
    cleanups = {ticket_id: absolute(files[att].url) for ticket_id, att in pending.items() if att in files}
    return photos, cleanups


def _waste_type_names(tickets):
    from app.models.masters.waste_masters.wastetype import WasteType

    ids = {w for t in tickets for w in (t.waste_type_ids or [])}
    return dict(WasteType.objects.filter(unique_id__in=ids).values_list("unique_id", "waste_type_name")) if ids else {}


def build_local_body(entry, obj, request=None):
    type_key, category, _model, name_field, column = entry
    closed, resolved = _status_ids()
    district = District.objects.filter(unique_id=obj.district_id).first()
    state = State.objects.filter(unique_id=obj.state_id).first()

    tickets = ComplaintTicket.objects.filter(is_deleted=False, **{column: obj.unique_id})
    ann = _count_annotations(closed, resolved)
    now = timezone.now()
    totals = tickets.aggregate(
        **ann,
        overdue=Count(
            "unique_id",
            filter=~Q(status_id__in=closed) & Q(next_escalation_due_at__lt=now),
        ),
    )
    open_by_level = _by_level(tickets.exclude(status_id__in=closed))

    # pins: open complaints plus anything closed in the last 30 days
    recent = now - timedelta(days=30)
    pin_qs = (
        tickets.filter(is_sensitive=False, latitude__isnull=False, longitude__isnull=False)
        .filter(~Q(status_id__in=closed) | Q(updated__gte=recent))
        .order_by("-created")
    )
    pin_rows = list(pin_qs[: MAX_PINS + 1])
    statuses = {s.unique_id: s for s in ComplaintStatus.objects.filter(is_deleted=False)}
    categories = dict(
        ComplaintCategory.objects.filter(unique_id__in={t.category_id for t in pin_rows})
        .values_list("unique_id", "category_name")
    )
    subcategories = dict(
        ComplaintSubcategory.objects.filter(unique_id__in={t.subcategory_id for t in pin_rows if t.subcategory_id})
        .values_list("unique_id", "subcategory_name")
    )
    photos, cleanups = _photos([t.unique_id for t in pin_rows[:MAX_PINS]], request)
    priorities = {
        p.unique_id: p for p in ComplaintPriority.objects.filter(unique_id__in={t.priority_id for t in pin_rows})
    }
    waste_type_names = _waste_type_names(pin_rows)
    pins = []
    for t in pin_rows[:MAX_PINS]:
        s = statuses.get(t.status_id)
        is_open = not (s and s.status_code in CLOSED_STATUS_CODES)
        end = None if is_open else (t.resolved_at or t.closed_at)
        pins.append({
            "ticket_no": t.ticket_no,
            "category": categories.get(t.category_id, ""),
            "subcategory": subcategories.get(t.subcategory_id, ""),
            "status": s.status_name if s else "",
            "status_code": s.status_code if s else "",
            "is_open": is_open,
            "is_escalated": t.is_escalated,
            "escalation_level": t.escalation_level,
            "is_overdue": bool(is_open and t.next_escalation_due_at and t.next_escalation_due_at < now),
            "created": t.created,
            "days_open": max(0, ((end or now) - t.created).days),
            "latitude": float(t.latitude),
            "longitude": float(t.longitude),
            "location_text": t.location_text or "",
            "photos": photos.get(t.unique_id, []),
            # the citizen's cleanup photo still waiting for the officer's check
            "cleanup_pending": cleanups.get(t.unique_id),
            "priority": getattr(priorities.get(t.priority_id), "priority_name", "") or "",
            "priority_code": getattr(priorities.get(t.priority_id), "priority_code", "") or "",
            "waste_types": [waste_type_names[w] for w in (t.waste_type_ids or []) if w in waste_type_names],
            "seen_count": t.seen_count,
        })

    return {
        "scope": "local_body",
        "state_id": obj.state_id,
        "state_name": state.name if state else "",
        "district_id": obj.district_id,
        "district_name": district.name if district else "",
        "local_body": {
            "id": obj.unique_id,
            "type": type_key,
            "category": category,
            "name": getattr(obj, name_field),
            "coordinates": _clean_coordinates(obj.coordinates),
        },
        "totals": totals,
        "by_status": _by_status(tickets),
        "hierarchy": _hierarchy({f"{type_key}_id": obj.unique_id}, open_by_level),
        "unassigned_open": open_by_level.get(0, 0),
        "tickets": pins,
        "tickets_truncated": len(pin_rows) > MAX_PINS,
    }


# ------------------------------------------------------------------
# Anonymous actions on a pin
# ------------------------------------------------------------------
def find_public_ticket(ticket_no):
    """The ticket behind a map pin, or None — sensitive tickets are never on
    the map, so they can't be acted on from it either."""
    if not ticket_no:
        return None
    return ComplaintTicket.objects.filter(ticket_no=ticket_no, is_deleted=False, is_sensitive=False).first()


def is_open(ticket):
    status = ticket.status
    return not (status and status.status_code in CLOSED_STATUS_CODES)


def mark_seen(ticket):
    """One more "I saw this too"; returns the new count."""
    ComplaintTicket.objects.filter(pk=ticket.pk).update(seen_count=F("seen_count") + 1)
    ticket.refresh_from_db(fields=["seen_count"])
    return ticket.seen_count
