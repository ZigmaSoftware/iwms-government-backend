"""Background job + Excel export API (see app/services/background_jobs.py).

GET  /api/v1/jobs/<job_id>/      status + result of the caller's own job
POST /api/v1/exports/excel/      {path, params, columns?, file_name, sheet_name}
                                 -> queues an export job on Celery, waits for
                                 it and answers with the .xlsx of every row
                                 of that list endpoint (202 + job id if it
                                 is still running after JOB_WAIT_SECONDS)
"""
from urllib.parse import quote, urlsplit

from django.core.files.storage import default_storage
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models.core_modules.background_job import BackgroundJob
from app.services.background_jobs import job_payload, owner_key, start_job, wait_for_job

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

API_PREFIX = "/api/v1/"


class BackgroundJobStatusView(APIView):
    def get(self, request, job_id):
        owner = owner_key(request.user)
        job = BackgroundJob.objects.filter(pk=job_id, owner=owner).first() if owner else None
        if job is None:
            return Response({"detail": "Job not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(job_payload(job))


def _export_path(raw):
    """The list endpoint to export, as an /api/v1/... path, or None."""
    path = urlsplit(str(raw or "").strip()).path
    if not path or ".." in path:
        return None
    if not path.startswith("/api/"):
        path = API_PREFIX + path.lstrip("/")
    if not path.startswith(API_PREFIX) or path.startswith((f"{API_PREFIX}jobs/", f"{API_PREFIX}exports/")):
        return None
    return path if path.endswith("/") else f"{path}/"


def _clean_params(raw):
    if not isinstance(raw, dict):
        return None
    params = {}
    for key, value in raw.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple)):
            params[str(key)] = [str(v) for v in value if v is not None]
        elif isinstance(value, (str, int, float, bool)):
            params[str(key)] = str(value).lower() if isinstance(value, bool) else str(value)
        else:
            return None
    return params


def _clean_columns(raw):
    """[{"header", "field"}] or None for "every field"; False if invalid."""
    if not raw:
        return None
    if not isinstance(raw, list):
        return False
    columns = []
    for column in raw:
        if not isinstance(column, dict):
            return False
        header, field = str(column.get("header") or "").strip(), str(column.get("field") or "").strip()
        if not header or not field:
            return False
        columns.append({"header": header[:255], "field": field[:200]})
    return columns


class ExcelExportView(APIView):
    """Download every row of a list endpoint as Excel in one request; the
    Celery worker builds the file while this request waits for it."""

    def post(self, request):
        path = _export_path(request.data.get("path"))
        if path is None:
            return Response({"path": "A list endpoint under /api/v1/ is required."}, status=400)
        params = _clean_params(request.data.get("params") or {})
        if params is None:
            return Response({"params": "Use an object of text, number or list values."}, status=400)
        columns = _clean_columns(request.data.get("columns"))
        if columns is False:
            return Response({"columns": "Use a list of {header, field}."}, status=400)
        file_name = str(request.data.get("file_name") or "export.xlsx")[:255]
        if not file_name.lower().endswith(".xlsx"):
            file_name = f"{file_name}.xlsx"

        job = start_job(
            request,
            kind=BackgroundJob.KIND_EXPORT,
            path=path,
            file_name=file_name,
            options={
                "params": params,
                "columns": columns,
                "sheet_name": str(request.data.get("sheet_name") or "Export")[:31],
            },
        )
        job = wait_for_job(job.unique_id, request.META.get("HTTP_AUTHORIZATION", ""))

        if job.status == BackgroundJob.STATUS_FAILED:
            return Response({"detail": job.error_message}, status=400)
        if job.status != BackgroundJob.STATUS_COMPLETED:
            # Very large export: hand back the job; the UI polls it instead.
            return Response(job_payload(job), status=status.HTTP_202_ACCEPTED)

        result = job.result or {}
        content = b""
        if result.get("stored_path"):
            with default_storage.open(result["stored_path"], "rb") as stored:
                content = stored.read()
        response = HttpResponse(content, content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(file_name)}"
        response["X-Row-Count"] = str(result.get("row_count", 0))
        if result.get("file_url"):
            # The worker's copy doubles as the audit-trail attachment.
            response["X-Archived-File-Url"] = result["file_url"]
        return response
