"""Run one complaint escalation sweep: move tickets past their
`next_escalation_due_at` up one Staff Hierarchy level.

Celery Beat already runs this every 30 seconds (iwms.complaint_sla_sweep).
Use this command for a one-off sweep, or from cron when Celery isn't running.
"""
from django.core.management.base import BaseCommand

from app.services.complaint_escalation_scheduler import run_complaint_sla_sweep


class Command(BaseCommand):
    help = "Auto-escalate overdue complaint tickets up the Staff Hierarchy."

    def handle(self, *args, **options):
        result = run_complaint_sla_sweep()
        if result.get("skipped"):
            self.stdout.write("Another sweep is running — skipped.")
            return
        self.stdout.write(self.style.SUCCESS(f"{result['escalated']} escalated."))
