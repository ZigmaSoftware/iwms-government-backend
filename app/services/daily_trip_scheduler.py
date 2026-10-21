"""Daily trip generation job.

Celery Beat calls `run_scheduled_daily_trip_job` every minute
(app/tasks/scheduler_tasks.py); it generates the day's trips once, after the
run_time configured in SchedulerConfig. Run status lives in the Django cache
(Redis) so every gunicorn worker and the Celery worker see the same state.
"""
import logging
import os
from datetime import datetime, time as datetime_time, timedelta

from django.core.cache import cache
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

JOB_NAME = "daily_trip_generation"
DEFAULT_RUN_TIME = "04:00"
STATUS_CACHE_KEY = f"iwms:scheduler:{JOB_NAME}:status"
# One auto run per day; kept two days so it outlives the day it guards.
AUTO_RUN_CLAIM_TIMEOUT = 2 * 24 * 60 * 60

_DEFAULT_STATUS = {
    "job_name": JOB_NAME,
    "last_run_at": None,
    "last_run_mode": None,
    "last_auto_run_at": None,
    "last_result": None,
    "last_error": None,
    "is_running": False,
    "last_auto_run_date": None,
}


def _parse_run_time(value):
    try:
        hour, minute = str(value or DEFAULT_RUN_TIME).split(":", 1)
        return datetime_time(hour=int(hour), minute=int(minute))
    except (TypeError, ValueError):
        return datetime_time(hour=4, minute=0)


def _next_run_after(now, run_time):
    candidate = datetime.combine(now.date(), run_time, tzinfo=now.tzinfo)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _try_database_lock(lock_name):
    if connection.vendor != "mysql":
        return True
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 0)", [lock_name])
        row = cursor.fetchone()
    return bool(row and row[0] == 1)


def _release_database_lock(lock_name):
    if connection.vendor != "mysql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT RELEASE_LOCK(%s)", [lock_name])


def _load_status():
    return {**_DEFAULT_STATUS, **(cache.get(STATUS_CACHE_KEY) or {})}


def _update_status(**changes):
    status = _load_status()
    status.update(changes)
    cache.set(STATUS_CACHE_KEY, status, timeout=None)


def run_daily_trip_job(target_date=None, force: bool = False):
    # Imported lazily: the command module imports models.
    from app.management.commands.generate_daily_trips import run_for_date

    target_date = target_date or timezone.localdate()
    mode = "manual" if force else "auto"
    lock_name = f"iwms:{JOB_NAME}:{target_date.isoformat()}:{mode}"
    if not _try_database_lock(lock_name):
        return {
            "skipped": True,
            "reason": "Another scheduler worker is already generating daily trips.",
        }

    _update_status(is_running=True, last_error=None)
    try:
        result = run_for_date(target_date=target_date, force=force)
        run_at = timezone.localtime().isoformat()
        changes = {"last_run_at": run_at, "last_run_mode": mode, "last_result": result}
        if not force:
            changes["last_auto_run_at"] = run_at
        _update_status(**changes)
        return result
    except Exception as exc:
        logger.exception("Daily trip scheduler failed")
        _update_status(last_error=str(exc))
        raise
    finally:
        _update_status(is_running=False)
        _release_database_lock(lock_name)


def run_scheduled_daily_trip_job():
    """Beat tick: run today's auto generation once, after the configured
    run_time. Returns None when there is nothing to do this minute."""
    run_time, is_enabled = _get_scheduler_config()
    if not is_enabled:
        return None
    now = timezone.localtime()
    if now < datetime.combine(now.date(), run_time, tzinfo=now.tzinfo):
        return None

    run_date = now.date().isoformat()
    # cache.add is atomic in Redis: only the first tick of the day claims
    # the run, even if a slow run overlaps the next tick.
    claim_key = f"iwms:scheduler:{JOB_NAME}:auto:{run_date}"
    if not cache.add(claim_key, True, timeout=AUTO_RUN_CLAIM_TIMEOUT):
        return None

    _update_status(last_auto_run_date=run_date)
    return run_daily_trip_job(target_date=now.date())


def scheduler_status():
    run_time, is_enabled = _get_scheduler_config()
    status = _load_status()
    status.update(
        enabled=bool(is_enabled),
        run_time=run_time.strftime("%H:%M"),
        next_run_at=_next_run_after(timezone.localtime(), run_time).isoformat(),
    )
    return status


def _get_scheduler_config():
    try:
        from app.models.core_modules.daily_operations.scheduler_config import SchedulerConfig
        config = SchedulerConfig.get_singleton()
        return config.run_time, config.is_enabled
    except Exception:
        return (
            _parse_run_time(os.getenv("DAILY_TRIP_SCHEDULER_TIME", DEFAULT_RUN_TIME)),
            True,
        )
