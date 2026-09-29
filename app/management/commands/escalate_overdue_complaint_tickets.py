"""Run one complaint escalation sweep: move tickets past their
`next_escalation_due_at` up one Staff Hierarchy level.

The in-process scheduler (app/services/complaint_escalation_scheduler.py)
already runs this every 30 seconds. Use this command when that scheduler is
disabled (ENABLE_COMPLAINT_ESCALATION_SCHEDULER=false), e.g. from cron:
`* * * * * cd /path/to/iwms-government-backend && python manage.py escalate_overdue_complaint_tickets`
"""
from django.core.management.base import BaseCommand

from app.services.complaint_escalation_scheduler import run_complaint_sla_sweep


class Command(BaseCommand):
    help = "Auto-escalate overdue complaint tickets up the Staff Hierarchy."

    def handle(self, *args, **options):
        result = run_complaint_sla_sweep()
        if result.get("skipped"):
            self.stdout.write("Another worker is running the sweep — skipped.")
            return
        self.stdout.write(self.style.SUCCESS(f"{result['escalated']} escalated."))
