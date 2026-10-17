"""Complaint SLA sweep.

Celery Beat runs this every COMPLAINT_ESCALATION_INTERVAL_SECONDS (default
30, see CELERY_BEAT_SCHEDULE) via app/tasks/scheduler_tasks.py: it
auto-escalates tickets past their current level's deadline
(`check_and_escalate_overdue_tickets`). The MySQL GET_LOCK keeps a sweep from
overlapping a manual `python manage.py escalate_overdue_complaint_tickets`.
"""
from app.services.daily_trip_scheduler import _release_database_lock, _try_database_lock

LOCK_NAME = "iwms:complaint_escalation_sweep"


def run_complaint_sla_sweep():
    """One sweep. Returns {"escalated"} or {"skipped": True} when another
    sweep holds the lock."""
    from app.services.complaint_escalation import check_and_escalate_overdue_tickets

    if not _try_database_lock(LOCK_NAME):
        return {"skipped": True}
    try:
        return {"escalated": check_and_escalate_overdue_tickets()}
    finally:
        _release_database_lock(LOCK_NAME)
