from django.db import models

from app.utils.comfun import generate_unique_id


def generate_background_job_id():
    return f"BGJOB-{generate_unique_id()}"


class BackgroundJob(models.Model):
    """A CSV bulk upload or an Excel export run by the Celery worker.

    Uploads answer 202 with the job id straight away and the UI polls
    `GET /api/v1/jobs/<job_id>/`; exports wait for the job and return the
    file in the same response. See app/services/background_jobs.py.
    """

    KIND_BULK_UPLOAD = "bulk_upload"
    KIND_EXPORT = "export"
    KIND_CHOICES = [
        (KIND_BULK_UPLOAD, "Bulk Upload"),
        (KIND_EXPORT, "Export"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]
    FINISHED_STATUSES = (STATUS_COMPLETED, STATUS_FAILED)

    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        default=generate_background_job_id,
        editable=False,
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True
    )
    # Who started it ("<model label>:<pk>"); only they can read the job.
    owner = models.CharField(max_length=150, db_index=True)
    # The API path the worker replays as the owner: the resource's
    # bulk-upload/ endpoint, or the list endpoint being exported.
    path = models.CharField(max_length=500)
    # Export: list query params, columns, sheet_name.
    # Both: host/scheme/client details so the replayed request matches.
    options = models.JSONField(default=dict, blank=True)
    file_name = models.CharField(max_length=255, blank=True, default="")
    # Bulk upload: the uploaded file, cleared once imported.
    upload_content = models.BinaryField(null=True, blank=True)
    # Bulk upload: the endpoint's usual response (counts, per-row errors).
    # Export: row_count, file_url, stored_path.
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "background_job"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.unique_id} {self.kind} ({self.status})"
