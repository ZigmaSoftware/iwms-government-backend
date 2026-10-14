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
