"""Routing + SLA resolution for complaint tickets.

Given a ticket's category/subcategory/location_node/priority/source, finds the
most specific matching ComplaintRoutingRule (to assign a team/user) and the
most specific matching ComplaintSlaRule (to compute due dates), then fills
only the ticket fields that are still empty — an explicit assignment or a
manually-set due date is never overwritten.
"""
from django.utils import timezone
from datetime import timedelta


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
        if not ticket.first_response_due_at and sla_rule.assign_within_minutes:
            ticket.first_response_due_at = now + timedelta(minutes=sla_rule.assign_within_minutes)
            updated_fields.append("first_response_due_at")
        if not ticket.sla_due_at and sla_rule.resolve_within_minutes:
            ticket.sla_due_at = now + timedelta(minutes=sla_rule.resolve_within_minutes)
            updated_fields.append("sla_due_at")

    if save and updated_fields:
        ticket.save(update_fields=updated_fields)

    return updated_fields
