"""In-process scheduler for the complaint SLA sweep.

Every COMPLAINT_ESCALATION_INTERVAL_SECONDS (default 30) it auto-escalates
tickets past their current level's deadline
(`check_and_escalate_overdue_tickets`). Same model as the daily trip
scheduler: a daemon thread per worker process, with a MySQL GET_LOCK so only
one gunicorn worker runs each sweep. Disable with
ENABLE_COMPLAINT_ESCALATION_SCHEDULER=false and schedule
`python manage.py escalate_overdue_complaint_tickets` from cron instead.
"""
import logging
import os
import sys
import threading
import time

from django.db import close_old_connections

from app.services.daily_trip_scheduler import _release_database_lock, _try_database_lock

logger = logging.getLogger(__name__)

LOCK_NAME = "iwms:complaint_escalation_sweep"
# Short so a ticket escalates close to the deadline its screen shows; each
# sweep is one indexed query on next_escalation_due_at.
DEFAULT_INTERVAL_SECONDS = 30
_scheduler_thread = None
_scheduler_lock = threading.Lock()

SKIP_COMMANDS = {
    "makemigrations",
    "migrate",
    "collectstatic",
    "shell",
    "test",
    "check",
    "seed",
    "showmigrations",
    "escalate_overdue_complaint_tickets",
    "backfill_escalation_due_dates",
}


def run_complaint_sla_sweep():
    """One sweep. Returns {"escalated"} or {"skipped": True} when another
    worker holds the lock."""
    from app.services.complaint_escalation import check_and_escalate_overdue_tickets

    if not _try_database_lock(LOCK_NAME):
        return {"skipped": True}
    try:
        return {"escalated": check_and_escalate_overdue_tickets()}
    finally:
        _release_database_lock(LOCK_NAME)


def _interval_seconds():
    try:
        seconds = float(os.getenv("COMPLAINT_ESCALATION_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    except ValueError:
        seconds = DEFAULT_INTERVAL_SECONDS
    return max(seconds, 10)


def _scheduler_loop():
    time.sleep(5)
    while True:
        close_old_connections()
        try:
            result = run_complaint_sla_sweep()
            if result.get("escalated"):
                logger.info("Complaint SLA sweep: %s", result)
        except Exception:
            logger.exception("Complaint SLA sweep failed")
        finally:
            close_old_connections()
        time.sleep(_interval_seconds())


def _should_start_scheduler():
    if os.getenv("ENABLE_COMPLAINT_ESCALATION_SCHEDULER", "true").lower() not in {"1", "true", "yes"}:
        return False
    if len(sys.argv) > 1 and sys.argv[1] in SKIP_COMMANDS:
        return False
    if "pytest" in sys.modules:
        return False
    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        return os.environ.get("RUN_MAIN") == "true"
    return True


def start_complaint_escalation_scheduler():
    global _scheduler_thread
    if not _should_start_scheduler():
        return False

    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return True
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            name="iwms-complaint-escalation-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()
        return True
