"""Routing + SLA resolution for complaint tickets.

Given a ticket's category/subcategory/flat geo (state/district/local body)/
priority/source, finds the most specific matching ComplaintRoutingRule (to
assign a user) and the most specific matching ComplaintSlaRule (whose
per-level windows pick the Staff Hierarchy entry level and escalation
deadlines — see app/services/complaint_escalation.py), then fills only the
ticket fields that are still empty — an explicit assignment is never
overwritten.
"""
from django.utils import timezone
from datetime import timedelta, time

from app.utils.staff_hierarchy import covers, row_scope, specificity

BUSINESS_START = time(9, 0)
BUSINESS_END = time(18, 0)
BUSINESS_WEEKDAY_LIMIT = 6  # weekday() >= this is off: Monday=0 ... Saturday=5 work, Sunday=6 is off


def _add_business_minutes(start, minutes):
    """Add `minutes` to `start`, counting only 09:00-18:00 on Mon-Sat."""
    remaining = minutes
    # Business hours are local (TIME_ZONE) — timezone.now() is UTC.
    current = timezone.localtime(start) if timezone.is_aware(start) else start
    # Move into the next open window if we start outside business hours.
    while current.time() < BUSINESS_START or current.time() >= BUSINESS_END or current.weekday() >= BUSINESS_WEEKDAY_LIMIT:
        if current.weekday() >= BUSINESS_WEEKDAY_LIMIT or current.time() >= BUSINESS_END:
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
            while current.weekday() >= BUSINESS_WEEKDAY_LIMIT:
                current += timedelta(days=1)
    return current


# Flat geo FK attnames shared by ComplaintRoutingRule and ComplaintTicket.
# An empty rule field means "any"; a set field must match the ticket exactly.
ROUTING_GEO_ATTNAMES = (
    "state_id",
    "district_id",
    "corporation_id",
    "municipality_id",
    "town_panchayat_id",
    "panchayat_union_id",
    "panchayat_id",
)


def _routing_matches(rule, ticket):
    if rule.subcategory_id and rule.subcategory_id != ticket.subcategory_id:
        return False
    for attname in ROUTING_GEO_ATTNAMES:
        rule_value = getattr(rule, attname, None)
        if rule_value and rule_value != getattr(ticket, attname, None):
            return False
    if rule.priority_id and rule.priority_id != ticket.priority_id:
        return False
    return True


def _routing_specificity(rule):
    return sum([
        bool(rule.subcategory_id),
        bool(rule.priority_id),
        *[bool(getattr(rule, attname, None)) for attname in ROUTING_GEO_ATTNAMES],
    ])


def _best_routing_rule(ticket):
    from app.models.core_modules.complaint_management.routing_rule import ComplaintRoutingRule

    candidates = ComplaintRoutingRule.objects.filter(
        is_deleted=False,
        is_active=True,
        category_id=ticket.category_id,
    )

    matching = [rule for rule in candidates if _routing_matches(rule, ticket)]
    if not matching:
        return None
    matching.sort(key=_routing_specificity, reverse=True)
    return matching[0]


def _sla_matches(rule, ticket, geo):
    if rule.subcategory_id and rule.subcategory_id != ticket.subcategory_id:
        return False
    if rule.priority_id and rule.priority_id != ticket.priority_id:
        return False
    if rule.source_id and rule.source_id != ticket.source_id:
        return False
    return covers(row_scope(rule), geo)


def _sla_specificity(rule):
    """Location first — a Panchayat/Corporation rule beats a District one,
    which beats a State-wide or unscoped one — then sub-category/priority/
    source."""
    scope = row_scope(rule)
    return (
        specificity(scope),
        len(scope),
        sum([bool(rule.subcategory_id), bool(rule.priority_id), bool(rule.source_id)]),
    )


def _best_sla_rule(ticket):
    from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule
    from app.services.complaint_escalation import ticket_geo

    candidates = ComplaintSlaRule.objects.filter(
        is_deleted=False,
        is_active=True,
        category_id=ticket.category_id,
    )

    geo = ticket_geo(ticket)
    matching = [rule for rule in candidates if _sla_matches(rule, ticket, geo)]
    if not matching:
        return None
    matching.sort(key=_sla_specificity, reverse=True)
    return matching[0]


def resolve_sla_rule(ticket, routing_rule=None):
    """The SLA rule governing `ticket`: the most specific matching rule, else
    the one pinned on the best routing rule.

    A routing rule's `sla_rule` is a catch-all (the seeder attaches the
    category-wide rule to a category-wide route), so it is only the fallback
    — a ticket whose sub-category has its own SLA must not silently get the
    category's slower target.
    """
    sla_rule = _best_sla_rule(ticket)
    if sla_rule:
        return sla_rule
    routing_rule = routing_rule or _best_routing_rule(ticket)
    return routing_rule.sla_rule if routing_rule and routing_rule.sla_rule_id else None


def apply_routing_and_sla(ticket, save=True):
    """Fill assigned_user, the entry-level assigned_staff and the escalation
    clock on `ticket` from the best-matching routing + SLA rules —
    only touching fields that are currently empty. Returns the list of
    updated field names.
    """
    from app.services.complaint_escalation import set_initial_escalation

    updated_fields = []

    routing_rule = _best_routing_rule(ticket)
    if routing_rule and routing_rule.user_id and not ticket.assigned_user_id:
        ticket.assigned_user_id = routing_rule.user_id
        updated_fields.append("assigned_user_id")

    sla_rule = resolve_sla_rule(ticket, routing_rule)

    auto_assigned = False
    if ticket.next_escalation_due_at is None and not ticket.escalation_level:
        escalation_fields = set_initial_escalation(ticket, sla_rule)
        auto_assigned = "assigned_staff_id" in escalation_fields
        updated_fields += escalation_fields

    if save and updated_fields:
        ticket.save(update_fields=updated_fields)

    if save and auto_assigned:
        from app.services import notification_service

        notification_service.notify(
            ticket,
            "ASSIGNED",
            f"Ticket {ticket.ticket_no} ({ticket.title or ticket.category.category_name}) has been assigned to you.",
            staff=ticket.assigned_staff,
        )

    return updated_fields
