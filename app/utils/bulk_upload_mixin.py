"""Single bulk-upload mechanism shared by every module.

Every list page uploads the same way: Excel -> CSV -> POST
``<resource>/bulk-upload/`` (multipart ``file``) -> standard response::

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
keeps the same response shape — the frontend does not care which one
served it.
"""

import csv
import io

from rest_framework.decorators import action
from rest_framework.response import Response


class BulkUploadMixin:
    """Generic serializer-driven bulk upload.

    Each CSV row is validated with the viewset's own serializer, so the
    rules are identical to creating the records one by one. Fully blank
    rows are skipped. Rejected rows echo the original CSV data so the UI
    can show *which* records failed and offer them for correction.
    """

    bulk_upload_message = "Bulk upload completed"

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        file = request.FILES.get("file") or request.data.get("file")

        if not file:
            return Response({"error": "CSV file is required"}, status=400)

        try:
            raw = file.read() if hasattr(file, "read") else file
            if isinstance(raw, bytes):
                decoded = raw.decode("utf-8-sig")
            else:
                decoded = str(raw)
        except Exception as exc:
            return Response(
                {"error": "Unable to decode CSV file", "detail": str(exc)},
                status=400,
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
            }
        )
