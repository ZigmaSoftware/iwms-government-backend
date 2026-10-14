"""Celery application for background tasks and periodic jobs.

Processes (each a separate container in docker-compose*.yml):
    celery -A config worker -l info     # runs queued tasks
    celery -A config beat -l info       # enqueues CELERY_BEAT_SCHEDULE jobs

Run exactly ONE beat process; it is the single scheduler for the whole
deployment. Tasks live in app/tasks/ and are configured from the CELERY_*
settings in config/settings.py.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("iwms")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
