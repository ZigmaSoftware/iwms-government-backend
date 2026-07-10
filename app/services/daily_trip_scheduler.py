import logging
import os
import sys
import threading
import time
from datetime import datetime, time as datetime_time, timedelta

from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

JOB_NAME = "daily_trip_generation"
DEFAULT_RUN_TIME = "04:00"
CONFIG_POLL_SECONDS = 60
_scheduler_thread = None
_scheduler_lock = threading.Lock()
_scheduler_wakeup = threading.Event()
_status = {
    "job_name": JOB_NAME,
    "enabled": False,
    "run_time": DEFAULT_RUN_TIME,
    "last_run_at": None,
    "last_run_mode": None,
    "last_auto_run_at": None,
    "last_result": None,
    "last_error": None,
    "next_run_at": None,
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


def run_daily_trip_job(target_date=None, force: bool = False):
    # Imported lazily: the command module imports models, which are not
    # loaded yet when this service is imported from AppConfig.ready().
    from app.management.commands.generate_daily_trips import run_for_date

    target_date = target_date or timezone.localdate()
    mode = "manual" if force else "auto"
    lock_name = f"iwms:{JOB_NAME}:{target_date.isoformat()}:{mode}"
    if not _try_database_lock(lock_name):
        return {
            "skipped": True,
            "reason": "Another scheduler worker is already generating daily trips.",
        }

    _status["is_running"] = True
    _status["last_error"] = None
    try:
        result = run_for_date(target_date=target_date, force=force)
        _status["last_run_at"] = timezone.localtime().isoformat()
        _status["last_run_mode"] = mode
        if not force:
            _status["last_auto_run_at"] = _status["last_run_at"]
        _status["last_result"] = result
        return result
    except Exception as exc:
        logger.exception("Daily trip scheduler failed")
        _status["last_error"] = str(exc)
        raise
    finally:
        _status["is_running"] = False
        _release_database_lock(lock_name)


def scheduler_status():
    return dict(_status)


def notify_scheduler_config_changed():
    _scheduler_wakeup.set()


def _get_scheduler_config():
    try:
        from app.models.schedule_masters.scheduler_config import SchedulerConfig
        config = SchedulerConfig.get_singleton()
        return config.run_time, config.is_enabled
    except Exception:
        return (
            _parse_run_time(os.getenv("DAILY_TRIP_SCHEDULER_TIME", DEFAULT_RUN_TIME)),
            True,
        )


def _scheduler_loop():
    time.sleep(1)
    while True:
        run_time, is_enabled = _get_scheduler_config()
        now = timezone.localtime()
        run_at_today = datetime.combine(now.date(), run_time, tzinfo=now.tzinfo)
        next_run = run_at_today if run_at_today > now else run_at_today + timedelta(days=1)

        _status["enabled"] = bool(is_enabled)
        _status["run_time"] = run_time.strftime("%H:%M")
        _status["next_run_at"] = next_run.isoformat()

        if is_enabled and now >= run_at_today:
            run_date = now.date().isoformat()
            if _status.get("last_auto_run_date") != run_date:
                try:
                    run_daily_trip_job(target_date=now.date())
                except Exception:
                    logger.exception("Scheduled daily trip generation failed")
                _status["last_auto_run_date"] = run_date
                continue

        seconds_until_next = max((next_run - now).total_seconds(), 1)
        _scheduler_wakeup.wait(min(seconds_until_next, CONFIG_POLL_SECONDS))
        _scheduler_wakeup.clear()


def _should_start_scheduler():
    if os.getenv("ENABLE_DAILY_TRIP_JOB_SCHEDULER", "true").lower() not in {
        "1",
        "true",
        "yes",
    }:
        return False

    management_commands = {
        "makemigrations",
        "migrate",
        "collectstatic",
        "shell",
        "test",
        "check",
        "seed",
        "showmigrations",
        "generate_daily_trips",
    }
    if len(sys.argv) > 1 and sys.argv[1] in management_commands:
        return False

    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        return os.environ.get("RUN_MAIN") == "true"

    return True


def start_daily_trip_scheduler():
    global _scheduler_thread
    if not _should_start_scheduler():
        return False

    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return True
        run_time = _parse_run_time(os.getenv("DAILY_TRIP_SCHEDULER_TIME", DEFAULT_RUN_TIME))
        _status["enabled"] = True
        _status["run_time"] = run_time.strftime("%H:%M")
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(),
            name="iwms-daily-trip-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()
        return True
