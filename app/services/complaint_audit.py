"""Complaint Audit: each ticket's lifecycle read back from its history rows.

Nothing here is stored — the audit is assembled on read from the ticket and
the history tables the ticket workflow already writes:

  * ComplaintStatusHistory     every status change, with remarks (the
                               resolution note is the remark on the change
                               to RESOLVED)
  * ComplaintReopenHistory     each reopen and its reason
  * ComplaintEscalationHistory each escalation (level, from/to whom, why,
                               auto or manual)
  * ComplaintAssignmentHistory reassignments, when any were recorded
  * ComplaintFeedback          the citizen's rating
  * CommonAudit                the DELETE entry (who/when) for a deleted
                               ticket, when one was recorded

`summarize_tickets` returns the list-row summary for many tickets at once
(one query per history table, not per ticket); `ticket_timeline` returns the
full event timeline and time-in-status for one ticket.

Government tickets carry no company/project: their scope is the flat geo
block on the ticket (state / district / local body), so the summary reports
those instead.

Actors: staff log in as StaffcreationOfficeDetails, not the auth User model,
so the history rows' *_by_user_id columns are only ever filled for auth-User
actors (see ticket_viewset._actor_user); a change made by a staff login has
no recorded actor and shows as unknown here.
"""
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from app.models.core_modules.complaint_management import (
    ComplaintAssignmentHistory,
    ComplaintCategory,
    ComplaintEscalationHistory,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintReopenHistory,
    ComplaintSource,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintSubcategory,
)
from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.services.complaint_escalation import CLOSED_STATUS_CODES
from app.utils.common_audit import CommonAudit

RESOLVED_CODE = "RESOLVED"
REOPENED_CODE = "REOPENED"
ESCALATED_CODE = "ESCALATED"
# A status-history row and the reopen/escalation/assignment row the same
# action wrote land within the same request; rows this close are treated as
# one event.
_SAME_ACTION_WINDOW = timedelta(seconds=60)

# (ticket column, master, name attribute, label) of the flat local-body
# masters — the ticket's "city", the level right below District. Only one is
# populated per ticket.
LOCAL_BODY_SOURCES = (
    ("corporation_id", Corporation, "corporation_name", "Corporation"),
    ("municipality_id", Municipality, "municipality_name", "Municipality"),
    ("town_panchayat_id", TownPanchayat, "town_panchayat_name", "Town Panchayat"),
    ("panchayat_union_id", PanchayatUnion, "union_name", "Panchayat Union"),
    ("panchayat_id", Panchayat, "panchayat_name", "Panchayat"),
)


def _seconds(start, end):
    if not start or not end:
        return None
    return max(int((end - start).total_seconds()), 0)


def _name_map(model, key_field, name_field, ids):
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return dict(model.objects.filter(**{f"{key_field}__in": ids}).values_list(key_field, name_field))


def ticket_local_body(ticket):
    """(column, unique_id, label) of the ticket's populated local-body
    column, or (None, None, None)."""
    for field, _model, _name_attr, label in LOCAL_BODY_SOURCES:
        value = getattr(ticket, field, None)
        if value:
            return field, value, label
    return None, None, None


def local_body_names(tickets):
    """{column: {unique_id: name}} for the local bodies `tickets` reference."""
    return {
        field: _name_map(model, "unique_id", name_attr, {getattr(t, field, None) for t in tickets})
        for field, model, name_attr, _label in LOCAL_BODY_SOURCES
    }


class _Names:
    """Bulk id -> display-name lookups for the actors and masters a set of
    tickets and history rows reference."""

    def __init__(self, *, user_ids=(), staff_ids=(), customer_ids=(), account_ids=()):
        account_ids = {a for a in account_ids if a}
        # An Account id (BaseMaster.created_by) is the user's unique_id or
        # the staff's staff_unique_id, so it resolves through the same two
        # maps.
        self.users = _name_map(get_user_model(), "unique_id", "username", set(user_ids) | account_ids)
        self.staff = _name_map(
            StaffcreationOfficeDetails, "staff_unique_id", "employee_name", set(staff_ids) | account_ids
        )
        self.customers = _name_map(CustomerCreation, "unique_id", "customer_name", customer_ids)

    def actor(self, *, staff_id=None, user_id=None, customer_id=None, system=False):
        name = (
            self.staff.get(staff_id)
            or self.users.get(user_id)
            or self.customers.get(customer_id)
        )
        if name:
            return name
        if system:
            return "System"
        return None

    def account(self, account_id):
        return self.staff.get(account_id) or self.users.get(account_id)


def _status_lookup():
    return {
        uid: {"code": code, "name": name}
        for uid, code, name in ComplaintStatus.objects.values_list("unique_id", "status_code", "status_name")
    }


def _histories(ticket_ids):
    by_ticket = lambda: defaultdict(list)  # noqa: E731
    status_rows, reopen_rows, escalation_rows, assignment_rows = (
        by_ticket(), by_ticket(), by_ticket(), by_ticket()
    )
    for row in ComplaintStatusHistory.objects.filter(ticket_id__in=ticket_ids, is_deleted=False).order_by("changed_at", "pk"):
        status_rows[row.ticket_id].append(row)
    for row in ComplaintReopenHistory.objects.filter(ticket_id__in=ticket_ids, is_deleted=False).order_by("reopened_at", "pk"):
        reopen_rows[row.ticket_id].append(row)
    for row in ComplaintEscalationHistory.objects.filter(ticket_id__in=ticket_ids, is_deleted=False).order_by("escalated_at", "pk"):
        escalation_rows[row.ticket_id].append(row)
    for row in ComplaintAssignmentHistory.objects.filter(ticket_id__in=ticket_ids, is_deleted=False).order_by("assigned_at", "pk"):
        assignment_rows[row.ticket_id].append(row)
    feedback = {
        row.ticket_id: row
        for row in ComplaintFeedback.objects.filter(ticket_id__in=ticket_ids, is_deleted=False)
    }
    return status_rows, reopen_rows, escalation_rows, assignment_rows, feedback


def _reporter_name(ticket, names):
    return names.customers.get(ticket.customer_id) or (ticket.profile_name or "").strip() or None


def summarize_tickets(tickets):
    """List-row audit summary for each ticket, in the order given.

    Each row is a plain dict (JSON-safe apart from datetimes, which DRF
    renders) with a stable set of keys — see types.ts on the frontend and
    the Audit Dashboard, which aggregates these rows.
    """
    tickets = list(tickets)
    if not tickets:
        return []
    ids = [t.unique_id for t in tickets]
    statuses = _status_lookup()
    status_rows, reopen_rows, escalation_rows, _, feedback = _histories(ids)

    categories = _name_map(ComplaintCategory, "unique_id", "category_name", {t.category_id for t in tickets})
    subcategories = _name_map(ComplaintSubcategory, "unique_id", "subcategory_name", {t.subcategory_id for t in tickets})
    priorities = _name_map(ComplaintPriority, "unique_id", "priority_name", {t.priority_id for t in tickets})
    sources = _name_map(ComplaintSource, "unique_id", "source_name", {t.source_id for t in tickets})
    states = _name_map(State, "unique_id", "name", {t.state_id for t in tickets})
    districts = _name_map(District, "unique_id", "name", {t.district_id for t in tickets})
    local_bodies = local_body_names(tickets)

    first_rows = {tid: rows[0] for tid, rows in status_rows.items() if rows}
    names = _Names(
        user_ids=[r.changed_by_user_id for r in first_rows.values()],
        staff_ids=[t.assigned_staff_id for t in tickets] + [t.escalated_to_staff_id for t in tickets],
        customer_ids=[t.customer_id for t in tickets] + [r.changed_by_customer_id for r in first_rows.values()],
        account_ids=[t.created_by for t in tickets],
    )

    now = timezone.now()
    summaries = []
    for t in tickets:
        rows = status_rows.get(t.unique_id, [])
        resolved = [r for r in rows if statuses.get(r.to_status_id, {}).get("code") == RESOLVED_CODE]
        reopens = reopen_rows.get(t.unique_id, [])
        escalations = escalation_rows.get(t.unique_id, [])
        status = statuses.get(t.status_id, {})
        completed_at = t.closed_at or t.resolved_at
        fb = feedback.get(t.unique_id)
        first = first_rows.get(t.unique_id)
        created_by = names.account(t.created_by) or (
            names.actor(
                user_id=first.changed_by_user_id,
                customer_id=first.changed_by_customer_id,
            )
            if first else None
        )
        local_body_field, local_body_id, local_body_type = ticket_local_body(t)

        summaries.append({
            "unique_id": t.unique_id,
            "ticket_no": t.ticket_no,
            "title": t.title,
            "state_id": t.state_id,
            "state_name": states.get(t.state_id),
            "district_id": t.district_id,
            "district_name": districts.get(t.district_id),
            "local_body_id": local_body_id,
            "local_body_name": local_bodies.get(local_body_field, {}).get(local_body_id),
            "local_body_type": local_body_type,
            "category_name": categories.get(t.category_id),
            "subcategory_name": subcategories.get(t.subcategory_id),
            "priority_name": priorities.get(t.priority_id),
            "source_name": sources.get(t.source_id),
            "status_code": status.get("code"),
            "status_name": status.get("name"),
            "reporter_name": _reporter_name(t, names),
            "created_by_name": created_by,
            "assigned_staff_name": names.staff.get(t.assigned_staff_id),
            # Whoever holds the ticket now that it has been escalated.
            "escalated_to_staff_name": names.staff.get(t.escalated_to_staff_id) if t.is_escalated else None,
            "created": t.created,
            "first_resolved_at": resolved[0].changed_at if resolved else None,
            "completed_at": completed_at,
            "closed_at": t.closed_at,
            # Time to the first resolution, and created -> final
            # resolution/closure (spans any reopen in between).
            "first_resolution_seconds": _seconds(t.created, resolved[0].changed_at) if resolved else None,
            "total_resolution_seconds": _seconds(t.created, completed_at),
            "open_seconds": None if completed_at else _seconds(t.created, now),
            "resolution_remarks": resolved[-1].remarks if resolved else None,
            "reopen_count": max(t.reopened_count or 0, len(reopens)),
            "last_reopen_reason": reopens[-1].reopen_reason if reopens else None,
            "escalation_count": len(escalations),
            "max_escalation_level": max((e.escalation_level for e in escalations), default=None),
            "auto_escalation_count": sum(1 for e in escalations if e.escalated_by_system),
            "feedback_rating": fb.rating if fb else None,
            "feedback_issue_solved": fb.is_issue_solved if fb else None,
            "is_deleted": t.is_deleted,
            # ComplaintTicket has no delete_reason column today; kept so the
            # row shape matches iwms-private and picks one up if added.
            "delete_reason": getattr(t, "delete_reason", None),
        })
    return summaries


def _role_names(staff_ids):
    """{staff_unique_id: government role display name} — the Staff
    Hierarchy role an escalation landed on."""
    from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType

    staff_roles = dict(
        StaffcreationOfficeDetails.objects.filter(
            staff_unique_id__in={s for s in staff_ids if s}
        ).values_list("staff_unique_id", "governmentusertype_id")
    )
    roles = {
        role.unique_id: role.get_name_display()
        for role in GovernmentStaffUserType.objects.filter(unique_id__in={r for r in staff_roles.values() if r})
    }
    return {staff_id: roles.get(role_id) for staff_id, role_id in staff_roles.items() if roles.get(role_id)}


def _near(at, others):
    return any(abs(at - other) <= _SAME_ACTION_WINDOW for other in others)


def _delete_audit(ticket):
    if not ticket.is_deleted:
        return None
    return (
        CommonAudit.objects.filter(object_id=ticket.unique_id, method="DELETE", success=True)
        .order_by("-createdAt")
        .first()
    )


def ticket_timeline(ticket):
    """Chronological lifecycle events for one ticket, plus time spent in
    each status."""
    statuses = _status_lookup()
    status_rows, reopen_rows, escalation_rows, assignment_rows, feedback = _histories([ticket.unique_id])
    rows = status_rows.get(ticket.unique_id, [])
    reopens = reopen_rows.get(ticket.unique_id, [])
    escalations = escalation_rows.get(ticket.unique_id, [])
    assignments = assignment_rows.get(ticket.unique_id, [])
    fb = feedback.get(ticket.unique_id)
    delete_audit = _delete_audit(ticket)

    names = _Names(
        user_ids=[r.changed_by_user_id for r in rows]
        + [r.reopened_by_user_id for r in reopens]
        + [e.escalated_to_user_id for e in escalations]
        + [e.escalated_by_user_id for e in escalations]
        + [a.from_user_id for a in assignments]
        + [a.to_user_id for a in assignments]
        + [a.assigned_by_id for a in assignments],
        staff_ids=[e.escalated_to_staff_id for e in escalations]
        + [e.escalated_from_staff_id for e in escalations]
        + [a.from_staff_id for a in assignments]
        + [a.to_staff_id for a in assignments],
        customer_ids=[r.changed_by_customer_id for r in rows]
        + [r.reopened_by_customer_id for r in reopens]
        + [ticket.customer_id, getattr(fb, "customer_id", None)],
        account_ids=[ticket.created_by],
    )
    role_names = _role_names([e.escalated_to_staff_id for e in escalations])

    def status_name(status_id):
        return statuses.get(status_id, {}).get("name")

    def status_code(status_id):
        return statuses.get(status_id, {}).get("code")

    events = []

    def add(kind, at, title, *, actor=None, remarks=None, details=None, allow_unknown_time=False):
        if at is None and not allow_unknown_time:
            return
        events.append({
            "type": kind,
            "at": at,
            "elapsed_seconds": _seconds(ticket.created, at),
            "title": title,
            "actor_name": actor,
            "remarks": remarks or None,
            "details": details or {},
        })

    creation_row = rows[0] if rows and rows[0].from_status_id is None else None
    add(
        "CREATED",
        ticket.created,
        "Complaint created",
        actor=names.account(ticket.created_by) or (
            names.actor(
                user_id=creation_row.changed_by_user_id,
                customer_id=creation_row.changed_by_customer_id,
            )
            if creation_row else None
        ),
        remarks=ticket.description,
        details={
            "title": ticket.title,
            "reporter": _reporter_name(ticket, names),
            "phone": ticket.wa_phone,
            "location": ticket.location_text,
            "status": status_name(creation_row.to_status_id) if creation_row else None,
        },
    )

    reopen_times = [r.reopened_at for r in reopens]
    escalation_times = [e.escalated_at for e in escalations]
    for row in rows:
        if row is creation_row:
            continue
        code = status_code(row.to_status_id)
        # The reopen / escalation rows below describe these changes in
        # more detail (reason, level, who), so don't list them twice.
        if code == REOPENED_CODE and _near(row.changed_at, reopen_times):
            continue
        if code == ESCALATED_CODE and _near(row.changed_at, escalation_times):
            continue
        if code == RESOLVED_CODE:
            kind, title = "RESOLVED", "Resolved"
        elif code in CLOSED_STATUS_CODES:
            kind, title = "CLOSED", status_name(row.to_status_id) or "Closed"
        else:
            kind = "STATUS_CHANGED"
            title = f"Status changed to {status_name(row.to_status_id) or 'unknown'}"
        add(
            kind,
            row.changed_at,
            title,
            actor=names.actor(
                user_id=row.changed_by_user_id,
                customer_id=row.changed_by_customer_id,
                system=row.changed_by_system,
            ),
            remarks=row.remarks,
            details={
                "from_status": status_name(row.from_status_id),
                "to_status": status_name(row.to_status_id),
            },
        )

    for row in reopens:
        add(
            "REOPENED",
            row.reopened_at,
            "Reopened",
            actor=names.actor(
                user_id=row.reopened_by_user_id,
                customer_id=row.reopened_by_customer_id,
            ),
            remarks=row.reopen_reason,
            details={"previous_status": status_name(row.previous_status_id)},
        )

    for row in escalations:
        level_name = role_names.get(row.escalated_to_staff_id)
        add(
            "ESCALATED",
            row.escalated_at,
            f"Escalated to level {row.escalation_level}" + (f" ({level_name})" if level_name else ""),
            actor=names.actor(
                user_id=row.escalated_by_user_id,
                system=row.escalated_by_system,
            ),
            remarks=row.reason,
            details={
                "level": row.escalation_level,
                "level_name": level_name,
                "from_level": row.escalated_from_level,
                "escalated_from": names.staff.get(row.escalated_from_staff_id),
                "escalated_to": names.actor(staff_id=row.escalated_to_staff_id, user_id=row.escalated_to_user_id),
                "automatic": row.escalated_by_system,
            },
        )

    for row in assignments:
        # escalate_ticket writes an assignment row alongside each escalation;
        # the ESCALATED event above already shows that hand-off.
        if any(
            e.escalated_to_staff_id == row.to_staff_id and abs(e.escalated_at - row.assigned_at) <= _SAME_ACTION_WINDOW
            for e in escalations
        ):
            continue
        from_name = names.staff.get(row.from_staff_id) or names.users.get(row.from_user_id)
        add(
            "ASSIGNED",
            row.assigned_at,
            "Reassigned" if (row.from_staff_id or row.from_user_id) else "Assigned",
            actor=names.users.get(row.assigned_by_id) or names.staff.get(row.assigned_by_id),
            remarks=row.assignment_reason,
            details={
                "from_staff": from_name,
                "to_staff": names.staff.get(row.to_staff_id) or names.users.get(row.to_user_id),
            },
        )

    if fb:
        add(
            "FEEDBACK",
            fb.submitted_at,
            "Citizen feedback",
            actor=names.customers.get(fb.customer_id),
            remarks=fb.feedback_text,
            details={"rating": fb.rating, "issue_solved": fb.is_issue_solved},
        )

    if ticket.is_deleted:
        add(
            "DELETED",
            # A delete with no CommonAudit DELETE row has no recorded time;
            # `updated` is no stand-in (the soft delete saves with
            # update_fields and skips it), so leave the time unknown rather
            # than invent one.
            delete_audit.createdAt if delete_audit else None,
            "Deleted",
            actor=(
                (getattr(delete_audit, "created_by_name", None) or delete_audit.createdBy)
                if delete_audit else None
            ),
            remarks=getattr(delete_audit, "delete_reason", None) or getattr(ticket, "delete_reason", None),
            allow_unknown_time=True,
        )

    # Unknown times (an unaudited delete) sort last.
    events.sort(key=lambda e: (e["at"] is None, e["at"] or ticket.created))
    return {"timeline": events, "status_durations": _status_durations(ticket, rows, statuses)}


def _status_durations(ticket, rows, statuses):
    """Total time the ticket sat in each status (a status entered more than
    once, e.g. after a reopen, is summed). The final status counts until now
    unless the ticket is finished."""
    totals = {}
    order = []
    now = timezone.now()
    for index, row in enumerate(rows):
        status = statuses.get(row.to_status_id, {})
        code = status.get("code")
        if index + 1 < len(rows):
            end = rows[index + 1].changed_at
        elif code == RESOLVED_CODE or code in CLOSED_STATUS_CODES or ticket.is_deleted:
            continue
        else:
            end = now
        key = row.to_status_id
        if key not in totals:
            order.append(key)
            totals[key] = {
                "status_code": code,
                "status_name": status.get("name"),
                "seconds": 0,
                "times_entered": 0,
            }
        totals[key]["seconds"] += _seconds(row.changed_at, end) or 0
        totals[key]["times_entered"] += 1
    return [totals[key] for key in order]
