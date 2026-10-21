"""Bulk uploads and Excel exports, run by the Celery worker.

Both replay an API request *as the user who started the job* through
Django's full middleware stack, so permissions, data scoping, audit logging
and created_by behave exactly as for a request from the browser. The user's
Authorization header travels only in the Celery message, never the DB.

Both are one API call: the request queues the job and *waits* for it
(`wait_for_job`), then answers with the result. A job still running after
JOB_WAIT_SECONDS answers 202 + job id instead and the UI polls
`GET /api/v1/jobs/<job_id>/`. A job no worker picks up within
JOB_PICKUP_SECONDS, or any job when no worker is running at all
(`workers_available`), is run in the request itself.

* Bulk upload - `POST <resource>/bulk-upload/` (wrapped in
  `run_in_background`). The worker re-posts the file with a signed
  X-Background-Job header; the endpoint then imports it as it always has,
  and its response is the upload's response.
* Export - `POST /api/v1/exports/excel/ {path, params, columns?}`. The
  worker does one internal GET of the list endpoint (all rows) and builds
  the .xlsx, flattened the same way the browser export does
  (utils/exportExcel.ts) or with only the given columns.
"""
import functools
import io
import json
import logging
import re
import time
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.handlers.base import BaseHandler
from django.test import RequestFactory
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.response import Response

from app.models.core_modules.background_job import BackgroundJob
from app.utils.file_archive import archive_bytes

logger = logging.getLogger(__name__)

JOB_HEADER = "X-Background-Job"
_JOB_META_KEY = "HTTP_X_BACKGROUND_JOB"
_SIGNING_SALT = "iwms.background-job"
# Matches the access-token lifetime (config/settings_jwt.py).
_SIGNATURE_MAX_AGE = 5 * 60 * 60
_CLIENT_META_KEYS = (
    "REMOTE_ADDR",
    "HTTP_X_FORWARDED_FOR",
    "HTTP_USER_AGENT",
    "HTTP_ACCEPT_LANGUAGE",
)

_WORKERS_CACHE_KEY = "iwms:celery:workers_available"

# Only followed when a list endpoint paginates even without page/limit.
EXPORT_MAX_PAGES = 100


class JobError(Exception):
    """A failure whose message is safe to show the user."""


# ------------------------------------------------------------------
# Starting jobs (web process)
# ------------------------------------------------------------------

def owner_key(user):
    if not getattr(user, "is_authenticated", False) or not hasattr(user, "_meta"):
        return ""
    return f"{user._meta.label}:{user.pk}"


def _client_options(request):
    return {
        "host": request.get_host(),
        "secure": request.is_secure(),
        "meta": {key: request.META[key] for key in _CLIENT_META_KEYS if request.META.get(key)},
    }


def workers_available():
    """True if a Celery worker is running. Pings the workers at most every
    few seconds (cached), so a request never waits for a missing worker."""
    from config.celery import app as celery_app

    if celery_app.conf.task_always_eager:
        return True
    alive = cache.get(_WORKERS_CACHE_KEY)
    if alive is None:
        try:
            # limit=1: return on the first reply instead of the full timeout.
            alive = bool(celery_app.control.ping(timeout=0.5, limit=1))
        except Exception:
            alive = False  # broker unreachable
        # Re-check a missing worker sooner, so one that starts is used quickly.
        cache.set(_WORKERS_CACHE_KEY, alive, 30 if alive else 5)
    return alive


def start_job(request, *, kind, path, file_name="", upload_content=None, options=None):
    """Create a BackgroundJob for `request.user` and queue it on Celery.
    With no worker running it is left unqueued; `wait_for_job` then runs it
    in the request straight away."""
    from app.tasks import enqueue
    from app.tasks.job_tasks import run_background_job

    job = BackgroundJob.objects.create(
        kind=kind,
        owner=owner_key(request.user),
        path=path,
        file_name=file_name,
        upload_content=upload_content,
        options={**(options or {}), "client": _client_options(request)},
    )
    if workers_available():
        enqueue(run_background_job, job.unique_id, request.META.get("HTTP_AUTHORIZATION", ""))
    return job


def wait_for_job(job_id, auth_header):
    """Block until the job finishes (or JOB_WAIT_SECONDS pass) and return it.

    With no worker running it runs here at once. If a worker was expected
    but hasn't picked the job up after JOB_PICKUP_SECONDS (it died, or is
    busy), run it here too rather than leave it queued.
    `run_job` claims the job atomically, so a worker that starts later
    cannot run it a second time.
    """
    started = time.monotonic()
    pickup_seconds = settings.JOB_PICKUP_SECONDS if workers_available() else 0
    while True:
        job = BackgroundJob.objects.get(pk=job_id)
        if job.status in BackgroundJob.FINISHED_STATUSES:
            return job
        elapsed = time.monotonic() - started
        if job.status == BackgroundJob.STATUS_QUEUED and elapsed >= pickup_seconds:
            logger.warning(
                "No Celery worker ran job %s - running it in the web process. "
                "Is the celery-worker running?",
                job_id,
            )
            run_job(job_id, auth_header)
            return BackgroundJob.objects.get(pk=job_id)
        if elapsed >= settings.JOB_WAIT_SECONDS:
            return job
        time.sleep(0.2)


def job_payload(job):
    data = {
        "job_id": job.unique_id,
        "kind": job.kind,
        "status": job.status,
        "file_name": job.file_name,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }
    if job.status == BackgroundJob.STATUS_COMPLETED and job.result:
        data.update(job.result)
    return data


def _is_worker_replay(request):
    signature = request.META.get(_JOB_META_KEY)
    if not signature:
        return False
    try:
        signed = signing.loads(signature, salt=_SIGNING_SALT, max_age=_SIGNATURE_MAX_AGE)
    except signing.BadSignature:
        return False
    return signed.get("path") == request.path


def run_in_background(bulk_upload):
    """Decorator for a viewset's `bulk_upload` action.

    A user's upload is stored as a BackgroundJob and queued; the worker's
    signed replay of the same request runs the wrapped import, unchanged.
    This request waits for it and answers with the import's usual response
    (202 + job id only if it is still running after JOB_WAIT_SECONDS).
    """

    @functools.wraps(bulk_upload)
    def wrapper(self, request, *args, **kwargs):
        if _is_worker_replay(request):
            return bulk_upload(self, request, *args, **kwargs)

        file = request.FILES.get("file") or request.data.get("file")
        if not file:
            return Response({"error": "CSV file is required"}, status=400)
        raw = file.read() if hasattr(file, "read") else file
        content = raw if isinstance(raw, bytes) else str(raw).encode("utf-8")

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        job = start_job(
            request,
            kind=BackgroundJob.KIND_BULK_UPLOAD,
            path=request.path,
            file_name=getattr(file, "name", None) or "bulk_upload.csv",
            upload_content=content,
        )
        job = wait_for_job(job.unique_id, auth_header)
        if job.status == BackgroundJob.STATUS_COMPLETED:
            return Response(job.result)
        if job.status == BackgroundJob.STATUS_FAILED:
            return Response({"error": job.error_message}, status=400)
        return Response(
            {**job_payload(job), "message": "Upload received. It is still being processed."},
            status=http_status.HTTP_202_ACCEPTED,
        )

    return wrapper


# ------------------------------------------------------------------
# Running jobs (Celery worker)
# ------------------------------------------------------------------

def run_job(job_id, auth_header):
    claimed = BackgroundJob.objects.filter(
        pk=job_id, status=BackgroundJob.STATUS_QUEUED
    ).update(status=BackgroundJob.STATUS_PROCESSING, started_at=timezone.now())
    if not claimed:
        # Already running when this message arrived means the worker died
        # mid-job and the broker redelivered it (acks_late). Re-running could
        # import rows twice, so stop and say so.
        BackgroundJob.objects.filter(
            pk=job_id, status=BackgroundJob.STATUS_PROCESSING
        ).update(
            status=BackgroundJob.STATUS_FAILED,
            error_message="The job was interrupted. Check the data before trying again.",
            finished_at=timezone.now(),
        )
        return

    job = BackgroundJob.objects.get(pk=job_id)
    try:
        if job.kind == BackgroundJob.KIND_EXPORT:
            job.result = _run_export(job, auth_header)
        else:
            job.result = _run_bulk_upload(job, auth_header)
        job.status = BackgroundJob.STATUS_COMPLETED
    except JobError as exc:
        job.status = BackgroundJob.STATUS_FAILED
        job.error_message = str(exc)
    except Exception:
        logger.exception("Background job %s failed", job_id)
        job.status = BackgroundJob.STATUS_FAILED
        job.error_message = "Something went wrong. Please try again."
    job.upload_content = None
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "result", "error_message", "upload_content", "finished_at"])


_handler = None


def _get_handler():
    global _handler
    if _handler is None:
        handler = BaseHandler()
        handler.load_middleware()
        _handler = handler
    return _handler


def _replay(client, method, path, auth_header, *, data=None, query=None, headers=None):
    """Run `method path` through the full middleware stack as the user the
    Authorization header belongs to; `client` is `_client_options()`."""
    extra = {
        **(client.get("meta") or {}),
        **(headers or {}),
        "HTTP_HOST": client.get("host") or "localhost",
        "HTTP_AUTHORIZATION": auth_header,
    }
    factory = RequestFactory()
    secure = bool(client.get("secure"))
    if method == "GET":
        request = factory.get(path, data=query or {}, secure=secure, **extra)
    else:
        request = factory.post(path, data=data or {}, secure=secure, **extra)
    response = _get_handler().get_response(request)
    try:
        body = json.loads(response.content or b"null")
    except ValueError:
        body = None

    if response.status_code == 401:
        raise JobError("Your session has expired. Please log in and try again.")
    if response.status_code == 403:
        raise JobError("You do not have permission to do this.")
    if response.status_code >= 400:
        detail = body.get("error") or body.get("detail") if isinstance(body, dict) else None
        raise JobError(str(detail or f"The request failed (HTTP {response.status_code})."))
    return body


def _run_bulk_upload(job, auth_header):
    signature = signing.dumps({"job": job.unique_id, "path": job.path}, salt=_SIGNING_SALT)
    upload = SimpleUploadedFile(job.file_name, bytes(job.upload_content or b""), content_type="text/csv")
    body = _replay(
        job.options.get("client") or {}, "POST", job.path, auth_header,
        data={"file": upload},
        headers={_JOB_META_KEY: signature},
    )
    if not isinstance(body, dict):
        raise JobError("The upload endpoint returned an unexpected response.")
    return body


def _run_export(job, auth_header):
    options = job.options
    rows = _fetch_all_rows(options.get("client") or {}, auth_header, job.path, options.get("params"))
    if not rows:
        return {"row_count": 0}
    content = build_xlsx(rows, options.get("sheet_name") or "Export", options.get("columns"))
    # Stored as the audit-trail copy too, so the browser never uploads it back.
    archived = archive_bytes(content, job.file_name or "export.xlsx", subdir="audit_attachments")
    if not archived.get("archived"):
        raise JobError("The exported file could not be saved. Please try again.")
    return {
        "row_count": len(rows),
        "file_url": archived["file_url"],
        "stored_path": f"audit_attachments/{archived['file_name']}",
    }


def _fetch_all_rows(client, auth_header, path, params):
    # No page/limit: list endpoints return every row in one response.
    query = dict(params or {})
    rows = []
    for _ in range(EXPORT_MAX_PAGES):
        body = _replay(client, "GET", path, auth_header, query=query)
        if isinstance(body, list):
            rows.extend(body)
            return rows
        if not isinstance(body, dict) or not isinstance(body.get("results"), list):
            raise JobError("The list endpoint returned an unexpected response.")
        rows.extend(body["results"])
        next_url = body.get("next")
        if not next_url:
            return rows
        parts = urlsplit(next_url)
        path, query = parts.path, parse_qs(parts.query, keep_blank_values=True)
    raise JobError("Too many rows to export. Narrow the filters and try again.")


# ------------------------------------------------------------------
# Excel output - mirrors frontend utils/exportExcel.ts + utils/capitalize.ts
# ------------------------------------------------------------------

_CAPITALIZED_FIELDS = {
    "address", "area", "description", "details", "label", "landmark", "name",
    "reason", "remark", "remarks", "street", "title",
}
_CAPITALIZED_SUFFIXES = tuple(f"_{field}" for field in _CAPITALIZED_FIELDS)
_NOT_CAPITALIZED_FIELDS = {
    "blob_name", "document_name", "file_name", "filename", "login_name",
    "object_name", "path_name", "storage_name", "user_name", "username",
}
_ILLEGAL_XLSX_CHARS = re.compile(r"[\000-\010]|[\013-\014]|[\016-\037]")
_ILLEGAL_SHEET_CHARS = re.compile(r"[\\/?*\[\]:]")


@functools.lru_cache(maxsize=1024)
def _capitalizes(field):
    field = field.strip().lower()
    if not field or field in _NOT_CAPITALIZED_FIELDS:
        return False
    return field in _CAPITALIZED_FIELDS or field.endswith(_CAPITALIZED_SUFFIXES)


def _capitalize(text):
    stripped = text.lstrip()
    if not stripped:
        return text
    lead = len(text) - len(stripped)
    return text[:lead] + stripped[0].upper() + stripped[1:]


def _cell_value(value, field):
    if value is None:
        return ""
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = _capitalize(value) if _capitalizes(field) else value
        return _ILLEGAL_XLSX_CHARS.sub("", text)
    if isinstance(value, list):
        value = [_capitalize(v) if isinstance(v, str) and _capitalizes(field) else v for v in value]
    return _ILLEGAL_XLSX_CHARS.sub("", json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":")))


@functools.lru_cache(maxsize=1024)
def _title(key):
    key = re.sub(r"[_-]+", " ", key)
    key = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
    key = re.sub(r"\s+", " ", key).strip()
    return re.sub(r"\b\w", lambda m: m.group(0).upper(), key)


def flatten_record(record, parent_key=""):
    flat = {}
    for key, value in record.items():
        export_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            flat.update(flatten_record(value, export_key))
        else:
            flat[_title(export_key)] = _cell_value(value, key)
    return flat


def _pick(record, field):
    value = record
    for part in field.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return _cell_value(value, field.rsplit(".", 1)[-1])


# Excel's per-cell text limit; longer values are cut rather than dropped.
_MAX_CELL_CHARS = 32767


def build_xlsx(records, sheet_name="Export", columns=None):
    """`columns` ([{"header", "field"}], dotted fields) picks and names the
    output columns; without it every field is exported, flattened."""
    import xlsxwriter

    records = [r for r in records if isinstance(r, dict)]
    if columns:
        headers = [c["header"] for c in columns]
        rows = [{c["header"]: _pick(r, c["field"]) for c in columns} for r in records]
    else:
        rows = [flatten_record(r) for r in records]
        headers = list(dict.fromkeys(key for row in rows for key in row))

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {
        "in_memory": True,
        # Cell text is data: never turn "=..." into a formula or text into links.
        "strings_to_formulas": False,
        "strings_to_urls": False,
        "strings_to_numbers": False,
    })
    sheet = workbook.add_worksheet(_ILLEGAL_SHEET_CHARS.sub("_", sheet_name)[:31] or "Export")
    if headers:
        sheet.write_row(0, 0, headers)
    for index, row in enumerate(rows, start=1):
        sheet.write_row(index, 0, [
            value[:_MAX_CELL_CHARS] if isinstance(value, str) else value
            for value in (row.get(header, "") for header in headers)
        ])
    workbook.close()
    return buffer.getvalue()
