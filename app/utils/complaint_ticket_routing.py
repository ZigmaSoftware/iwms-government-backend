"""Routing + SLA resolution for complaint tickets.

Given a ticket's category/subcategory/location_node/priority/source, finds the
most specific matching ComplaintRoutingRule (to assign a team/user) and the
most specific matching ComplaintSlaRule (to compute due dates), then fills
only the ticket fields that are still empty — an explicit assignment or a
manually-set due date is never overwritten.
"""
from django.db.models import Max
from django.utils import timezone
from datetime import timedelta, time

BUSINESS_START = time(9, 0)
BUSINESS_END = time(18, 0)
BUSINESS_WEEKDAY_LIMIT = 6  # Monday=0 ... Saturday=5 are working days, Sunday=6 is off


def _add_business_minutes(start, minutes):
    """Add `minutes` to `start`, counting only 09:00-18:00 on Mon-Sat."""
    remaining = minutes
    current = start
    # Move into the next open window if we start outside business hours.
    while current.time() < BUSINESS_START or current.time() >= BUSINESS_END or current.weekday() > BUSINESS_WEEKDAY_LIMIT:
        if current.weekday() > BUSINESS_WEEKDAY_LIMIT or current.time() >= BUSINESS_END:
            current = (current + timedelta(days=1)).replace(
                hour=BUSINESS_START.hour, minute=BUSINESS_START.minute, second=0, microsecond=0
            )
        else:
            current = current.replace(
                hour=BUSINESS_START.hour, minute=BUSINESS_START.minute, second=0, microsecond=0
            )

    while remaining > 0:
        end_of_day = current.replace(hour=BUSINESS_END.hour, minute=BUSINESS_END.minute, second=0, microsecond=0)
        minutes_left_today = int((end_of_day - current).total_seconds() // 60)
        if remaining <= minutes_left_today:
            current += timedelta(minutes=remaining)
            remaining = 0
        else:
            remaining -= minutes_left_today
            current = (current + timedelta(days=1)).replace(
                hour=BUSINESS_START.hour, minute=BUSINESS_START.minute, second=0, microsecond=0
            )
            while current.weekday() > BUSINESS_WEEKDAY_LIMIT:
                current += timedelta(days=1)
    return current


def _routing_matches(rule, ticket):
    if rule.subcategory_id and rule.subcategory_id != ticket.subcategory_id:
        return False
    if rule.location_node_id and rule.location_node_id != ticket.location_node_id:
        return False
    if rule.priority_id and rule.priority_id != ticket.priority_id:
        return False
    return True


def _routing_specificity(rule):
    return sum([
        bool(rule.subcategory_id),
        bool(rule.location_node_id),
        bool(rule.priority_id),
    ])


def _best_routing_rule(ticket):
    from app.models.complaint_ticket.routing_rule import ComplaintRoutingRule

    candidates = ComplaintRoutingRule.objects.filter(
        is_deleted=False,
        is_active=True,
        category_id=ticket.category_id,
    ).select_related("team", "user", "sla_rule")

    matching = [rule for rule in candidates if _routing_matches(rule, ticket)]
    if not matching:
        return None
    matching.sort(key=_routing_specificity, reverse=True)
    return matching[0]


def _sla_matches(rule, ticket):
    if rule.subcategory_id and rule.subcategory_id != ticket.subcategory_id:
        return False
    if rule.priority_id and rule.priority_id != ticket.priority_id:
        return False
    if rule.source_id and rule.source_id != ticket.source_id:
        return False
    return True


def _sla_specificity(rule):
    return sum([
        bool(rule.subcategory_id),
        bool(rule.priority_id),
        bool(rule.source_id),
    ])


def _best_sla_rule(ticket):
    from app.models.complaint_ticket.sla_rule_master import ComplaintSlaRule

    candidates = ComplaintSlaRule.objects.filter(
        is_deleted=False,
        is_active=True,
        category_id=ticket.category_id,
    )

    matching = [rule for rule in candidates if _sla_matches(rule, ticket)]
    if not matching:
        return None
    matching.sort(key=_sla_specificity, reverse=True)
    return matching[0]


def apply_routing_and_sla(ticket, save=True):
    """Fill assigned_team/assigned_user and sla_due_at/first_response_due_at
    on `ticket` from the best-matching routing + SLA rules — only touching
    fields that are currently empty. Returns the list of updated field names.
    """
    updated_fields = []
    now = timezone.now()

    routing_rule = None
    if not ticket.assigned_team_id:
        routing_rule = _best_routing_rule(ticket)
        if routing_rule:
            ticket.assigned_team = routing_rule.team
            updated_fields.append("assigned_team")
            if routing_rule.user_id and not ticket.assigned_user_id:
                ticket.assigned_user = routing_rule.user
                updated_fields.append("assigned_user")

    sla_rule = (routing_rule.sla_rule if routing_rule and routing_rule.sla_rule_id else None)
    if not sla_rule:
        sla_rule = _best_sla_rule(ticket)

    if sla_rule:
        add_minutes = _add_business_minutes if sla_rule.working_hours_only else (
            lambda start, minutes: start + timedelta(minutes=minutes)
        )
        if not ticket.first_response_due_at and sla_rule.assign_within_minutes:
            ticket.first_response_due_at = add_minutes(now, sla_rule.assign_within_minutes)
            updated_fields.append("first_response_due_at")
        if not ticket.sla_due_at and sla_rule.resolve_within_minutes:
            ticket.sla_due_at = add_minutes(now, sla_rule.resolve_within_minutes)
            updated_fields.append("sla_due_at")

    if save and updated_fields:
        ticket.save(update_fields=updated_fields)

    return updated_fields


def perform_escalation(ticket, target_team=None, reason=None, actor_user=None, by_system=False):
    """Escalate `ticket` to `target_team` (or the current team's `escalates_to`).

    Shared by the manual `/escalate/` API action and the automated SLA-breach
    detection job so both paths write identical history rows. Raises
    ValueError if there is no team to escalate to.
    """
    from app.models.complaint_ticket.status_master import ComplaintStatus
    from app.models.complaint_ticket.status_history import ComplaintStatusHistory
    from app.models.complaint_ticket.assignment_history import ComplaintAssignmentHistory
    from app.models.complaint_ticket.escalation_history import ComplaintEscalationHistory
    from app.services import notification_service

    current_team = ticket.assigned_team
    target = target_team or (current_team.escalates_to if current_team else None)
    if not target:
        raise ValueError("Already at the top of the escalation chain.")

    escalated_status = ComplaintStatus.objects.filter(status_code="ESCALATED", is_deleted=False).first()

    from_team = current_team
    from_staff = ticket.assigned_staff

    last_level = (
        ticket.escalation_history.aggregate(m=Max("escalation_level"))["m"]
        if hasattr(ticket, "escalation_history") else None
    )
    base_level = last_level or (current_team.escalation_level if current_team else 1)
    next_level = base_level + 1

    ticket.assigned_team = target
    ticket.assigned_staff = target.lead_staff
    old_status = ticket.status
    if escalated_status:
        ticket.status = escalated_status
        ticket.save(update_fields=["assigned_team", "assigned_staff", "status"])
    else:
        ticket.save(update_fields=["assigned_team", "assigned_staff"])

    escalation = ComplaintEscalationHistory.objects.create(
        ticket=ticket,
        escalation_level=next_level,
        escalated_from_team=from_team,
        escalated_to_team=target,
        escalated_to_staff=target.lead_staff,
        reason=reason,
        escalated_by_system=by_system,
    )
    ComplaintAssignmentHistory.objects.create(
        ticket=ticket,
        from_team=from_team,
        to_team=target,
        from_staff=from_staff,
        to_staff=target.lead_staff,
        assigned_by=actor_user,
        assignment_reason=reason or ("SLA breach auto-escalation" if by_system else "Escalated"),
    )
    if escalated_status:
        ComplaintStatusHistory.objects.create(
            ticket=ticket,
            from_status=old_status,
            to_status=escalated_status,
            changed_by_user=actor_user,
            changed_by_system=by_system,
            remarks=f"Escalated to {target.team_name}" + (f": {reason}" if reason else ""),
            visible_to_citizen=True,
        )

    new_staff = target.lead_staff
    if new_staff and (not from_staff or new_staff.staff_unique_id != from_staff.staff_unique_id):
        notification_service.notify(
            ticket,
            "ESCALATED_TO",
            f"Ticket {ticket.ticket_no} escalated to you (Level {next_level}, {target.team_name})." + (
                f" Reason: {reason}" if reason else ""
            ),
            staff=new_staff,
        )
    if from_staff and (not new_staff or from_staff.staff_unique_id != new_staff.staff_unique_id):
        notification_service.notify(
            ticket,
            "ESCALATED",
            f"Ticket {ticket.ticket_no} has been escalated to {target.team_name}." + (
                f" Reason: {reason}" if reason else ""
            ),
            staff=from_staff,
        )
    return escalation
