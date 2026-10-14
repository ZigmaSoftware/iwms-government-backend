"""Bulk uploads and Excel exports (see app/services/background_jobs.py)."""
from celery import shared_task


@shared_task(name="iwms.run_background_job")
def run_background_job(job_id, auth_header):
    from app.services.background_jobs import run_job

    run_job(job_id, auth_header)
