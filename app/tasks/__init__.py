"""Celery tasks (see config/celery.py).

Queue work through `enqueue` / `enqueue_on_commit` rather than calling
`.delay()` directly: if Redis is unreachable they run the task in-process
instead, so an email or push is never lost because the broker is down.
"""
import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def enqueue(task, *args, **kwargs):
    """Queue `task` on the Celery broker; run it inline if the broker is down."""
    try:
        task.apply_async(args=args, kwargs=kwargs)
    except Exception:
        logger.exception("Celery broker unavailable - running %s inline", task.name)
        task.apply(args=args, kwargs=kwargs)


def enqueue_on_commit(task, *args, **kwargs):
    """`enqueue` once the current DB transaction commits (immediately when
    not inside one), so a rolled-back change never sends a notification."""
    transaction.on_commit(lambda: enqueue(task, *args, **kwargs))


# Imported for task registration (Celery autodiscovers `app.tasks`).
from app.tasks import job_tasks, notification_tasks, scheduler_tasks  # noqa: E402,F401
