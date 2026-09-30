"""One-off backfill: put existing open tickets on the escalation clock.

Tickets created before hierarchy escalation existed (or before their SLA
rule had escalation levels configured) have no `next_escalation_due_at`, so
the sweep never looks at them. This runs `apply_routing_and_sla` on each
open one, which only fills empty fields — the entry-level assignee (if none
yet), `escalation_level` and `next_escalation_due_at`. Safe to re-run.
"""
from django.core.management.base import BaseCommand

from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.services.complaint_escalation import CLOSED_STATUS_CODES
from app.utils.complaint_ticket_routing import apply_routing_and_sla


class Command(BaseCommand):
    help = "Set escalation level/due date on open complaint tickets that have none."

    def handle(self, *args, **options):
        closed_status_ids = ComplaintStatus.objects.filter(status_code__in=CLOSED_STATUS_CODES).values("unique_id")
        tickets = ComplaintTicket.objects.filter(
            is_deleted=False, next_escalation_due_at__isnull=True, escalation_level=0,
        ).exclude(status_id__in=closed_status_ids)

        updated = skipped = 0
        for ticket in tickets:
            if "next_escalation_due_at" in apply_routing_and_sla(ticket, save=True):
                updated += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"{updated} ticket(s) put on the escalation clock; {skipped} skipped "
            "(no SLA escalation level or no covering staff)."
        ))
