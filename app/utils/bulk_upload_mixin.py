"""Single bulk-upload mechanism shared by every module.

Every list page uploads the same way: Excel -> CSV -> POST
``<resource>/bulk-upload/`` (multipart ``file``) -> 202 with a ``job_id``.
The Celery worker imports the file (``run_in_background``, see
app/services/background_jobs.py) and ``GET /api/v1/jobs/<job_id>/`` then
returns the standard response::

    {
        "message": "Bulk upload completed",
        "success_count": <int>,
        "error_count": <int>,
        "total_count": <int>,
        "errors": [{"row": <csv data-row, 1-based>, "error": ...,
                    "data": <original csv row>}],
    }

Mix this into any ``ModelViewSet`` to enable the endpoint. Modules with
complex import rules (FK-by-name resolution, QR generation, password
hashing, ...) override ``bulk_upload`` with their own implementation that
keeps the same response shape and is also decorated with
``@run_in_background`` — the frontend does not care which one served it.
"""

import csv
import io

from rest_framework.decorators import action
from rest_framework.response import Response

from app.services.background_jobs import run_in_background
from app.utils.file_archive import archive_bytes


class BulkUploadMixin:
    """Generic serializer-driven bulk upload.

    Each CSV row is validated with the viewset's own serializer, so the
    rules are identical to creating the records one by one. Fully blank
    rows are skipped. Rejected rows echo the original CSV data so the UI
    can show *which* records failed and offer them for correction.
    """

    bulk_upload_message = "Bulk upload completed"
    # Subdirectory (under media/) where the received file is archived for
    # audit reference. Override per viewset when useful.
    bulk_upload_archive_subdir = "bulk_uploads"

    def _bulk_upload_archive_dir(self) -> str:
        endpoint = (
            getattr(self, "AUDIT_ENDPOINT", None)
            or getattr(self, "throttle_scope", None)
            or type(self).__name__.replace("ViewSet", "")
        )
        safe = "".join(
            ch if ch.isalnum() or ch in ("-", "_") else "_"
            for ch in str(endpoint)
        ).strip("_") or "uploads"
        return f"{self.bulk_upload_archive_subdir}/{safe.lower()}"

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    @run_in_background
    def bulk_upload(self, request):
        file = request.FILES.get("file") or request.data.get("file")

        if not file:
            return Response({"error": "CSV file is required"}, status=400)

        try:
            raw = file.read() if hasattr(file, "read") else file
            if isinstance(raw, bytes):
                content = raw
                decoded = raw.decode("utf-8-sig")
            else:
                decoded = str(raw)
                content = decoded.encode("utf-8")
            upload_name = getattr(file, "name", None) or "bulk_upload.csv"
        except Exception as exc:
            return Response(
                {"error": "Unable to decode CSV file", "detail": str(exc)},
                status=400,
            )

        # Keep a server-side copy so the audit trail can show/download the
        # exact file that was uploaded. Never blocks the import itself.
        archived = archive_bytes(
            content, upload_name, subdir=self._bulk_upload_archive_dir()
        )

        try:
            reader = csv.DictReader(io.StringIO(decoded))
            if not reader.fieldnames:
                return Response(
                    {"error": "The uploaded file does not contain any data rows."},
                    status=400,
                )
            rows = list(reader)
        except Exception as exc:
            return Response(
                {"error": "Unable to parse CSV file", "detail": str(exc)},
                status=400,
            )

        success_count = 0
        errors: list[dict] = []

        for index, raw_row in enumerate(rows, start=1):
            row = {
                key: value
                for key, value in (raw_row or {}).items()
                if key
            }
            values = [
                value.strip() if isinstance(value, str) else value
                for value in row.values()
            ]
            if not any(
                value not in (None, "") for value in values
            ):
                continue

            payload = {
                key: (None if value == "" else value)
                for key, value in row.items()
            }

            serializer = self.get_serializer(data=payload)
            if serializer.is_valid():
                try:
                    # Route through perform_create so per-row audit logging
                    # and cache invalidation behave exactly like creating
                    # the records one by one.
                    self.perform_create(serializer)
                except Exception as exc:
                    errors.append(
                        {"row": index, "error": str(exc), "data": row}
                    )
                    continue
                success_count += 1
            else:
                errors.append(
                    {"row": index, "error": serializer.errors, "data": row}
                )

        return Response(
            {
                "message": self.bulk_upload_message,
                "success_count": success_count,
                "error_count": len(errors),
                "total_count": success_count + len(errors),
                "errors": errors,
                "file_name": upload_name,
                # Server-side copy of the uploaded file for audit reference.
                "file_url": archived.get("file_url") if archived.get("archived") else None,
            }
        )
