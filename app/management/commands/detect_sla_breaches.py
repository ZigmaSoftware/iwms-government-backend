"""Flag overdue complaint tickets and auto-escalate them past their SLA rule's
escalation window.

This is the single source of truth for SLA breach detection — meant to be run
on a schedule via OS cron/systemd timer (this project has no Celery/task
queue), e.g. every 5 minutes: `python manage.py detect_sla_breaches`.

Idempotent: a ticket already flagged `sla_breached=True` is skipped, and
auto-escalation only fires once per breach because `perform_escalation`
reassigns the ticket to the next team, which changes what `escalates_to`
matching produces on the next run.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from app.models.complaint_ticket.ticket import ComplaintTicket
from app.models.complaint_ticket.comment import ComplaintComment
from app.utils.complaint_ticket_routing import perform_escalation, _best_sla_rule

OPEN_STATUS_EXCLUDE = ["RESOLVED", "CLOSED", "REJECTED", "CANCELLED"]


def run(logger=None):
    log = logger or (lambda msg: None)
    now = timezone.now()

    overdue = ComplaintTicket.objects.filter(
        is_deleted=False,
        sla_breached=False,
        sla_due_at__isnull=False,
        sla_due_at__lt=now,
    ).exclude(status__status_code__in=OPEN_STATUS_EXCLUDE).select_related("status", "assigned_team")

    breached_count = 0
    escalated_count = 0

    for ticket in overdue:
        with transaction.atomic():
            ticket.sla_breached = True
            ticket.sla_breached_at = now
            ticket.save(update_fields=["sla_breached", "sla_breached_at"])
            ComplaintComment.objects.create(
                ticket=ticket,
                comment_text=f"SLA breached — resolution was due {ticket.sla_due_at}.",
                is_internal=True,
            )
            breached_count += 1

            sla_rule = _best_sla_rule(ticket)
            overdue_minutes = (now - ticket.sla_due_at).total_seconds() / 60
            if sla_rule and sla_rule.escalation_after_minutes and overdue_minutes >= sla_rule.escalation_after_minutes:
                target = sla_rule.escalation_team
                try:
                    perform_escalation(
                        ticket,
                        target_team=target,
                        reason="Automated SLA breach escalation",
                        by_system=True,
                    )
                    escalated_count += 1
                except ValueError:
                    pass  # already at the top of the escalation chain

    log(f"SLA breach sweep: {breached_count} newly breached, {escalated_count} auto-escalated.")
    return {"breached": breached_count, "escalated": escalated_count}


class Command(BaseCommand):
    help = "Flag complaint tickets past their sla_due_at and auto-escalate per SLA rule config."

    def handle(self, *args, **options):
        run(logger=self.stdout.write)
