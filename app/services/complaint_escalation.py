"""Staff-Hierarchy-driven assignment and auto-escalation for complaint tickets.

Levels are `StaffHierarchy.hierarchy_level` numbers. For a ticket's area, a
role's level is the `hierarchy_level` of its most specific covering hierarchy
row (see app/utils/staff_hierarchy.py). A role that only appears as a
`reports_to` head — e.g. an Admin at the top of the chain, which has no row
of its own — sits one level above the highest role reporting to it, so the
chain's head is still reachable.

Each SLA rule configures a resolve window per level
(`ComplaintSlaEscalationLevel`). Only enabled levels take part:

- On creation the ticket goes to the lowest enabled level that has a staff
  member covering the ticket's area, and `next_escalation_due_at` is set
  from that level's window.
- If the ticket is still open at `next_escalation_due_at`, the sweep
  (`check_and_escalate_overdue_tickets`, run by the in-process scheduler or
  the `escalate_overdue_complaint_tickets` command) hops it to the next
  enabled level above that has covering staff. Running out of levels stops
  escalating.

A staff member covers a ticket when every geo column set on their record
matches the ticket's area — a District Officer covers every panchayat in the
district, a Panchayat Supervisor only their own panchayat.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from app.utils.staff_hierarchy import (
    LEVEL_ANCESTORS,
    LOCAL_BODY_SCOPE_FIELDS,
    SCOPE_FIELDS,
    complete_geo,
    covers,
    resolve_entry,
    scope_government_level,
    specificity,
)

# Ticket statuses that stop the escalation clock.
CLOSED_STATUS_CODES = ("RESOLVED", "CLOSED", "REJECTED", "CANCELLED")

# Geo columns on StaffcreationOfficeDetails (staff carry no country).
STAFF_GEO_FIELDS = tuple(field for field in SCOPE_FIELDS if field != "country_id")


# ------------------------------------------------------------------
# Hierarchy levels
# ------------------------------------------------------------------
def _hierarchy_rows():
    from app.models.superadmin.role_management.staffHierarchy import StaffHierarchy

    return list(StaffHierarchy.objects.filter(is_active=True, is_deleted=False))


def ticket_geo(ticket):
    return complete_geo({field: getattr(ticket, field, None) for field in SCOPE_FIELDS})


def role_levels(geo, rows=None):
    """{governmentusertype_id: level} for the chain that applies in `geo`."""
    rows = _hierarchy_rows() if rows is None else rows
    levels = {}
    entries = []
    for role_id in {row.governmentusertype_id for row in rows}:
        entry = resolve_entry(rows, role_id, geo)
        if entry:
            levels[role_id] = entry.hierarchy_level
            entries.append(entry)

    heads = {}
    for entry in entries:
        head = entry.reports_to_governmentusertype_id
        if head and head not in levels:
            heads[head] = max(heads.get(head, 0), entry.hierarchy_level + 1)
    levels.update(heads)
    return levels


def hierarchy_level_options(geo=None):
    """Staff Hierarchy levels with the role names at each — for the SLA rule
    screen's escalation-level editor.

    With `geo` (an SLA rule's scope) only the chain that applies in that area
    is listed; without it, every level configured anywhere.
    """
    from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType

    rows = _hierarchy_rows()
    by_level = {}
    if geo:
        geo = complete_geo(geo)
        # Unscoped rows apply everywhere, but only roles at the area's own
        # government level or a broader one can ever hold its tickets (no
        # Panchayat Operator for a Corporation).
        area_level = scope_government_level(geo)
        allowed = None if area_level is None else {area_level, *LEVEL_ANCESTORS.get(area_level, ())}
        role_gov_levels = dict(GovernmentStaffUserType.objects.values_list("unique_id", "level"))
        for role, level in role_levels(geo, rows).items():
            if allowed is None or role_gov_levels.get(role) in allowed:
                by_level.setdefault(level, set()).add(role)
    else:
        own_roles = {row.governmentusertype_id for row in rows}
        for row in rows:
            by_level.setdefault(row.hierarchy_level, set()).add(row.governmentusertype_id)
            head = row.reports_to_governmentusertype_id
            if head and head not in own_roles:
                by_level.setdefault(row.hierarchy_level + 1, set()).add(head)

    names = dict(
        GovernmentStaffUserType.objects.filter(
            unique_id__in={role for roles in by_level.values() for role in roles}
        ).values_list("unique_id", "name")
    )
    return [
        {
            "level": level,
            "roles": sorted(
                ({"unique_id": role, "name": names.get(role, role)} for role in roles),
                key=lambda role: role["name"],
            ),
        }
        for level, roles in sorted(by_level.items())
    ]


def _staff_scope(staff):
    return {field: getattr(staff, field) for field in STAFF_GEO_FIELDS if getattr(staff, field, None)}


def _staff_covers(staff, geo):
    """Whether `staff` handles tickets from area `geo`: every state/district/
    area-type column set on the staff record matches, and — if the record
    names local bodies — the ticket's local body is one of them. (Some
    records carry more than one local body, e.g. a union officer also tagged
    to a panchayat; any of them counts.)"""
    scope = _staff_scope(staff)
    broad = {field: value for field, value in scope.items() if field not in LOCAL_BODY_SCOPE_FIELDS}
    if not covers(broad, geo):
        return False
    local_bodies = {(field, value) for field, value in scope.items() if field in LOCAL_BODY_SCOPE_FIELDS}
    if not local_bodies:
        return True
    return any(geo.get(field) == value for field, value in local_bodies)


def staff_for_level(level, geo, levels):
    """The staff member who handles `level` in area `geo`, or None. Prefers
    the most locally scoped match (a Panchayat Supervisor over a
    District-wide one), then login-enabled staff."""
    from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails

    roles = [role for role, role_level in levels.items() if role_level == level]
    if not roles:
        return None
    candidates = [
        staff
        for staff in StaffcreationOfficeDetails.objects.filter(
            governmentusertype_id__in=roles, active_status=True, is_deleted=False,
        )
        if _staff_covers(staff, geo)
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda staff: (-specificity(_staff_scope(staff)), not staff.login_enabled, staff.staff_unique_id)
    )
    return candidates[0]


# ------------------------------------------------------------------
# SLA windows
# ------------------------------------------------------------------
def compute_due(minutes, working_hours_only, start=None):
    """Deadline `minutes` after `start` (default now), honouring the SLA
    rule's business-hours flag."""
    from app.utils.complaint_ticket_routing import _add_business_minutes

    if not minutes:
        return None
    start = start or timezone.now()
    if working_hours_only:
        return _add_business_minutes(start, minutes)
    return start + timedelta(minutes=minutes)


def _enabled_levels(sla_rule):
    """[(level, resolve_within_minutes)] of the rule's enabled levels, lowest first."""
    if not sla_rule:
        return []
    return list(
        sla_rule.escalation_levels.filter(is_enabled=True).values_list("level", "resolve_within_minutes")
    )


def _level_due(sla_rule, level, start=None):
    minutes = dict(_enabled_levels(sla_rule)).get(level)
    return compute_due(minutes, sla_rule.working_hours_only if sla_rule else False, start)


def _next_level_staff(ticket, sla_rule, above_level):
    """(level, staff) for the first enabled level above `above_level` with
    staff covering the ticket's area, or (None, None)."""
    geo = ticket_geo(ticket)
    levels = role_levels(geo)
    for level, _minutes in _enabled_levels(sla_rule):
        if level <= above_level:
            continue
        staff = staff_for_level(level, geo, levels)
        if staff:
            return level, staff
    return None, None


# ------------------------------------------------------------------
# Lifecycle hooks
# ------------------------------------------------------------------
def set_initial_escalation(ticket, sla_rule):
    """Assign a new ticket to its entry level and start the escalation clock.

    Keeps an explicit `assigned_staff_id`, placing the ticket at that staff
    member's own level. Returns the list of changed field names (unsaved).
    """
    from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails

    if not _enabled_levels(sla_rule):
        return []

    updated = []
    if ticket.assigned_staff_id:
        staff = StaffcreationOfficeDetails.objects.filter(staff_unique_id=ticket.assigned_staff_id).first()
        level = role_levels(ticket_geo(ticket)).get(getattr(staff, "governmentusertype_id", None))
        if level is None:
            level, _ = _next_level_staff(ticket, sla_rule, above_level=0)
    else:
        level, staff = _next_level_staff(ticket, sla_rule, above_level=0)
        if staff:
            ticket.assigned_staff_id = staff.staff_unique_id
            updated.append("assigned_staff_id")

    if level is None:
        return updated

    ticket.escalation_level = level
    ticket.next_escalation_due_at = _level_due(sla_rule, level)
    return updated + ["escalation_level", "next_escalation_due_at"]


def _level_started_at(ticket):
    """When the ticket arrived at its current level: its last escalation to
    that level or its last reopen, whichever is later, else its creation."""
    from app.models.core_modules.complaint_management.escalation_history import ComplaintEscalationHistory
    from app.models.core_modules.complaint_management.reopen_history import ComplaintReopenHistory

    moments = [ticket.created]
    escalated = ComplaintEscalationHistory.objects.filter(
        ticket_id=ticket.unique_id, escalation_level=ticket.escalation_level, is_deleted=False,
    ).order_by("-escalated_at").values_list("escalated_at", flat=True).first()
    reopened = ComplaintReopenHistory.objects.filter(
        ticket_id=ticket.unique_id, is_deleted=False,
    ).order_by("-reopened_at").values_list("reopened_at", flat=True).first()
    moments += [moment for moment in (escalated, reopened) if moment]
    return max(moments)


def reschedule_open_tickets(sla_rule):
    """Apply `sla_rule`'s current windows to the open tickets it governs, so
    editing a rule's timings (or adding a more specific rule for an area)
    takes effect on tickets already in flight — counted from when each
    ticket reached its current level. Tickets already past the new deadline
    escalate on the next sweep. Returns the number of tickets changed."""
    from app.models.core_modules.complaint_management.status_master import ComplaintStatus
    from app.models.core_modules.complaint_management.ticket import ComplaintTicket
    from app.utils.complaint_ticket_routing import apply_routing_and_sla, resolve_sla_rule

    closed_status_ids = ComplaintStatus.objects.filter(status_code__in=CLOSED_STATUS_CODES).values("unique_id")
    tickets = ComplaintTicket.objects.filter(
        is_deleted=False, category_id=sla_rule.category_id,
    ).exclude(status_id__in=closed_status_ids)

    changed = 0
    for ticket in tickets:
        governing = resolve_sla_rule(ticket)
        if not governing or governing.pk != sla_rule.pk:
            continue
        if not ticket.escalation_level:
            # Never placed on the chain (e.g. no levels configured before).
            if "next_escalation_due_at" in apply_routing_and_sla(ticket, save=True):
                changed += 1
            continue
        due = _level_due(governing, ticket.escalation_level, start=_level_started_at(ticket))
        if due != ticket.next_escalation_due_at:
            ComplaintTicket.objects.filter(pk=ticket.pk).update(next_escalation_due_at=due)
            changed += 1
    return changed


def stop_escalation_clock(ticket):
    """Call once a ticket is resolved/closed — nothing left to escalate."""
    if ticket.next_escalation_due_at:
        ticket.next_escalation_due_at = None
        ticket.save(update_fields=["next_escalation_due_at"])


def restart_escalation_clock(ticket):
    """Call on reopen: the current level gets a fresh window."""
    from app.utils.complaint_ticket_routing import resolve_sla_rule

    due = _level_due(resolve_sla_rule(ticket), ticket.escalation_level)
    if due != ticket.next_escalation_due_at:
        ticket.next_escalation_due_at = due
        ticket.save(update_fields=["next_escalation_due_at"])


# ------------------------------------------------------------------
# Who may act
# ------------------------------------------------------------------
def is_passed_over(ticket, user):
    """True when `user` is a staff member the ticket has escalated past —
    its first assignee or an earlier escalatee, now that a higher level owns
    it. They keep seeing the ticket but may no longer resolve/close/assign/
    escalate it; only the level it currently sits with can."""
    from app.models.core_modules.complaint_management.escalation_history import ComplaintEscalationHistory

    staff_uid = getattr(user, "staff_unique_id", None)
    if not staff_uid or not ticket.is_escalated or ticket.escalated_to_staff_id == staff_uid:
        return False
    if ticket.assigned_staff_id == staff_uid:
        return True
    return ComplaintEscalationHistory.objects.filter(
        ticket_id=ticket.unique_id, escalated_to_staff_id=staff_uid, is_deleted=False,
    ).exists()


# ------------------------------------------------------------------
# Escalation
# ------------------------------------------------------------------
def _level_label(level, staff):
    return f"L{level}" + (f" - {staff.employee_name}" if staff else "")


@transaction.atomic
def escalate_ticket(ticket, reason=None, actor_user=None, by_system=True):
    """Escalate `ticket` to the next enabled hierarchy level above its
    current one. Locks the ticket row so the sweep and a manual escalation
    can't double-hop it. Raises ValueError when there is no next level."""
    from app.models.core_modules.complaint_management.assignment_history import ComplaintAssignmentHistory
    from app.models.core_modules.complaint_management.escalation_history import ComplaintEscalationHistory
    from app.models.core_modules.complaint_management.status_history import ComplaintStatusHistory
    from app.models.core_modules.complaint_management.status_master import ComplaintStatus
    from app.models.core_modules.complaint_management.ticket import ComplaintTicket
    from app.services import notification_service
    from app.services.push_notification_service import send_push_to_customer
    from app.utils.complaint_ticket_routing import resolve_sla_rule

    ticket = ComplaintTicket.objects.select_for_update().get(pk=ticket.pk)
    sla_rule = resolve_sla_rule(ticket)
    to_level, to_staff = _next_level_staff(ticket, sla_rule, above_level=ticket.escalation_level)
    if to_staff is None:
        raise ValueError("No higher Staff Hierarchy level is configured for this ticket.")

    from_level = ticket.escalation_level
    from_staff = ticket.responsible_staff
    actor_id = getattr(actor_user, "unique_id", None)

    ticket.escalation_level = to_level
    ticket.is_escalated = True
    ticket.escalated_to_staff_id = to_staff.staff_unique_id
    ticket.next_escalation_due_at = _level_due(sla_rule, to_level)
    update_fields = ["escalation_level", "is_escalated", "escalated_to_staff_id", "next_escalation_due_at"]

    old_status_id = ticket.status_id
    escalated_status = ComplaintStatus.objects.filter(status_code="ESCALATED", is_deleted=False).first()
    if escalated_status:
        ticket.status_id = escalated_status.unique_id
        update_fields.append("status_id")
    ticket.save(update_fields=update_fields)

    ComplaintEscalationHistory.objects.create(
        ticket_id=ticket.unique_id,
        escalation_level=to_level,
        escalated_from_level=from_level or None,
        escalated_from_staff_id=getattr(from_staff, "staff_unique_id", None),
        escalated_to_staff_id=to_staff.staff_unique_id,
        escalated_by_user_id=actor_id,
        reason=reason,
        escalated_by_system=by_system,
    )
    ComplaintAssignmentHistory.objects.create(
        ticket_id=ticket.unique_id,
        from_staff_id=getattr(from_staff, "staff_unique_id", None),
        to_staff_id=to_staff.staff_unique_id,
        assigned_by_id=actor_id,
        assignment_reason=reason or ("SLA breach auto-escalation" if by_system else "Escalated"),
    )
    if escalated_status:
        verb = "Auto-escalated" if by_system else "Escalated"
        ComplaintStatusHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_status_id=old_status_id,
            to_status_id=escalated_status.unique_id,
            changed_by_user_id=actor_id,
            changed_by_system=by_system,
            remarks=f"{verb} {_level_label(from_level, from_staff)} -> {_level_label(to_level, to_staff)}"
            + (f": {reason}" if reason else ""),
            visible_to_citizen=True,
        )

    notification_service.notify(
        ticket,
        "ESCALATED_TO",
        f"Ticket {ticket.ticket_no} escalated to you (Level {to_level})"
        + (f" from {from_staff.employee_name}" if from_staff else "")
        + (f". Reason: {reason}" if reason else "."),
        staff=to_staff,
    )
    if from_staff and from_staff.staff_unique_id != to_staff.staff_unique_id:
        notification_service.notify(
            ticket,
            "ESCALATED",
            f"Ticket {ticket.ticket_no} has been escalated to {to_staff.employee_name} (Level {to_level})."
            + (f" Reason: {reason}" if reason else ""),
            staff=from_staff,
        )
    send_push_to_customer(
        ticket.customer,
        "Grievance update",
        f"Your ticket {ticket.ticket_no} has been escalated for closer attention.",
        data={"event": "ticket_escalated", "ticket_id": str(ticket.unique_id)},
    )
    return ticket


def check_and_escalate_overdue_tickets():
    """Escalate every open ticket past its `next_escalation_due_at` one hop.
    Returns the number escalated."""
    from app.models.core_modules.complaint_management.status_master import ComplaintStatus
    from app.models.core_modules.complaint_management.ticket import ComplaintTicket

    closed_status_ids = ComplaintStatus.objects.filter(status_code__in=CLOSED_STATUS_CODES).values("unique_id")
    overdue = ComplaintTicket.objects.filter(
        is_deleted=False, next_escalation_due_at__lt=timezone.now(),
    ).exclude(status_id__in=closed_status_ids)

    count = 0
    for ticket in overdue:
        try:
            escalate_ticket(ticket, reason="SLA breach - auto escalation", by_system=True)
            count += 1
        except ValueError:
            # Top of the chain for this ticket — clear the deadline so the
            # sweep stops picking it up every run.
            ComplaintTicket.objects.filter(pk=ticket.pk).update(next_escalation_due_at=None)
    return count
