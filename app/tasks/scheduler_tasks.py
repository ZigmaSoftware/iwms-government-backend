"""Periodic jobs, enqueued by Celery Beat (CELERY_BEAT_SCHEDULE in settings)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="iwms.daily_trip_generation_tick")
def daily_trip_generation_tick():
    from app.services.daily_trip_scheduler import run_scheduled_daily_trip_job

    result = run_scheduled_daily_trip_job()
    if result is not None:
        logger.info("Daily trip generation: %s", result)


@shared_task(name="iwms.complaint_sla_sweep")
def complaint_sla_sweep():
    from app.services.complaint_escalation_scheduler import run_complaint_sla_sweep

    result = run_complaint_sla_sweep()
    if result.get("escalated"):
        logger.info("Complaint SLA sweep: %s", result)


@shared_task(name="iwms.close_idle_login_sessions")
def close_idle_login_sessions():
    """Stamp logout time on web sessions whose browser never reported the
    logout (tab closed, machine asleep) and on sessions past their lifetime."""
    from app.services.login_session import close_stale_sessions

    closed = close_stale_sessions()
    if closed:
        logger.info("Closed %s stale login session(s)", closed)


@shared_task(name="iwms.process_retrip_timeouts")
def process_retrip_timeouts():
    """Re-Trip decision window: remind / escalate to the supervisor, then
    expire requests nobody decided (app/services/retrip_timeout_service.py)."""
    from app.services.retrip_timeout_service import process_retrip_timeouts as run

    result = run()
    if any(result.values()):
        logger.info("Re-Trip timeouts: %s", result)
    return result
