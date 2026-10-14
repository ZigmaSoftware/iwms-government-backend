"""Single bulk-upload mechanism (BulkUploadMixin) — response contract.

Every module uploads the same way: CSV -> POST <resource>/bulk-upload/.
The Celery worker imports it while the request waits, and the response is
{message, success_count, error_count, total_count, errors[]} (or 202 +
job_id when it takes longer than JOB_WAIT_SECONDS).
"""
import io

import jwt
from django.core.files.uploadedfile import SimpleUploadedFile
import pytest
from django.conf import settings
from rest_framework.test import APIClient

from app.models.masters.transport_masters.fuel import Fuel
from app.models.superadmin_masters.auth_user import User

FUELS_URL = "/api/v1/transport-masters/fuels/"


@pytest.fixture
def api_client(db):
    user = User.objects.create_user(username="bulk-tester", is_superuser=True)
    token = jwt.encode({"unique_id": user.unique_id}, settings.SECRET_KEY, algorithm="HS256")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def _csv(text):
    return io.BytesIO(text.encode("utf-8"))


def test_bulk_upload_missing_file(api_client):
    res = api_client.post(FUELS_URL + "bulk-upload/", {}, format="multipart")
    assert res.status_code == 400
    assert res.json()["error"] == "CSV file is required"


def test_bulk_upload_success_and_rejected_rows(api_client):
    # Celery runs eagerly in tests, so the job finishes within the request.
    res = api_client.post(
        FUELS_URL + "bulk-upload/",
        {"file": SimpleUploadedFile("fuels.csv", _csv("fuel_type,description\nDiesel,for trucks\n,Diesel without name\n").getvalue(), content_type="text/csv")},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["success_count"] == 1
    assert body["error_count"] == 1
    assert body["total_count"] == 2
    assert len(body["errors"]) == 1
    failed = body["errors"][0]
    assert failed["row"] == 2
    assert failed["data"]["description"] == "Diesel without name"
    assert Fuel.objects.filter(fuel_type="Diesel").exists()
    # The uploaded file is archived server-side for audit reference.
    assert (body["file_url"] or "").endswith(".csv")
    assert "bulk_uploads" in (body["file_url"] or "")


@pytest.fixture
def plain_client(db):
    user = User.objects.create_user(username="no-grants", is_superuser=False)
    token = jwt.encode({"unique_id": user.unique_id}, settings.SECRET_KEY, algorithm="HS256")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def test_bulk_upload_requires_import_not_add(plain_client):
    """POST .../bulk-upload/ is gated on "import", single create on "add"."""
    res = plain_client.post(
        FUELS_URL + "bulk-upload/",
        {"file": SimpleUploadedFile("f.csv", _csv("fuel_type\nPetrol\n").getvalue(), content_type="text/csv")},
        format="multipart",
    )
    assert res.status_code == 403, res.content
    assert res.json().get("action") == "import"

    res = plain_client.post(FUELS_URL, {"fuel_type": "Petrol"}, format="json")
    assert res.status_code == 403, res.content
    assert res.json().get("action") == "add"


def test_audit_attachments_archive_and_reject(api_client):
    res = api_client.post(
        "/api/v1/audits/common-audit/attachments/",
        {"file": SimpleUploadedFile("export.xlsx", _csv("a,b\n1,2\n").getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        format="multipart",
    )
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["archived"] is True
    assert (body["file_url"] or "").endswith(".xlsx")

    res = api_client.post(
        "/api/v1/audits/common-audit/attachments/",
        {"file": SimpleUploadedFile("run.exe", _csv("x\n").getvalue(), content_type="application/octet-stream")},
        format="multipart",
    )
    assert res.status_code == 400, res.content


@pytest.fixture
def no_worker(settings, monkeypatch):
    """Nothing consumes the queue and the request stops waiting at once."""
    import app.tasks

    settings.JOB_WAIT_SECONDS = 0
    settings.JOB_PICKUP_SECONDS = 60
    monkeypatch.setattr(app.tasks, "enqueue", lambda task, *args, **kwargs: None)


def test_forged_job_header_does_not_bypass_the_queue(api_client, no_worker):
    """Only the worker's signed replay imports in-request."""
    res = api_client.post(
        FUELS_URL + "bulk-upload/",
        {"file": SimpleUploadedFile("f.csv", _csv("fuel_type\nPetrol\n").getvalue(), content_type="text/csv")},
        format="multipart",
        HTTP_X_BACKGROUND_JOB="forged",
    )
    assert res.status_code == 202, res.content
    assert not Fuel.objects.filter(fuel_type="Petrol").exists()


def test_job_is_only_visible_to_its_owner(api_client, plain_client, no_worker):
    res = api_client.post(
        FUELS_URL + "bulk-upload/",
        {"file": SimpleUploadedFile("f.csv", _csv("fuel_type\nPetrol\n").getvalue(), content_type="text/csv")},
        format="multipart",
    )
    job_id = res.json()["job_id"]
    assert plain_client.get(f"/api/v1/jobs/{job_id}/").status_code == 404
    assert api_client.get(f"/api/v1/jobs/{job_id}/").status_code == 200


def _xlsx_rows(response):
    from openpyxl import load_workbook

    return list(load_workbook(io.BytesIO(response.content)).active.values)


def test_export_returns_xlsx_in_one_request(api_client, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    Fuel.objects.create(fuel_type="diesel", description="for trucks")
    Fuel.objects.create(fuel_type="petrol", description="for cars")

    res = api_client.post(
        "/api/v1/exports/excel/",
        {"path": "/transport-masters/fuels/", "params": {"search": "diesel"}, "file_name": "fuels", "sheet_name": "Fuels"},
        format="json",
    )
    assert res.status_code == 200, res.content
    assert res["X-Row-Count"] == "1"
    assert "fuels.xlsx" in res["Content-Disposition"]
    assert res["X-Archived-File-Url"].endswith("fuels.xlsx")

    rows = _xlsx_rows(res)
    headers = rows[0]
    assert "Fuel Type" in headers
    # Same capitalisation as the browser export (description is a text field).
    assert rows[1][headers.index("Description")] == "For trucks"


def test_export_rejects_paths_outside_the_api(api_client):
    # Relative paths ("/masters/fuels/") are taken as under /api/v1/.
    for path in ("", "/api/v2/fuels/", "/api/v1/jobs/x/", "/api/v1/../admin/", "exports/excel/"):
        res = api_client.post("/api/v1/exports/excel/", {"path": path}, format="json")
        assert res.status_code == 400, (path, res.content)


def test_export_with_selected_columns(api_client, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    Fuel.objects.create(fuel_type="diesel", description="for trucks")

    res = api_client.post(
        "/api/v1/exports/excel/",
        {
            "path": "/transport-masters/fuels/",
            "columns": [{"header": "Fuel", "field": "fuel_type"}, {"header": "Notes", "field": "description"}],
        },
        format="json",
    )
    assert res.status_code == 200, res.content
    assert _xlsx_rows(res) == [("Fuel", "Notes"), ("diesel", "For trucks")]


def test_slow_export_falls_back_to_job_polling(api_client, no_worker):
    """If the worker hasn't finished within JOB_WAIT_SECONDS the export
    answers 202 + job id instead of holding the request open."""
    res = api_client.post("/api/v1/exports/excel/", {"path": "/transport-masters/fuels/"}, format="json")
    assert res.status_code == 202, res.content
    body = res.json()
    assert body["kind"] == "export" and body["status"] == "queued"
    assert api_client.get(f"/api/v1/jobs/{body['job_id']}/").json()["status"] == "queued"


def test_job_runs_in_request_when_no_worker_picks_it_up(api_client, settings, monkeypatch):
    """No worker running: after JOB_PICKUP_SECONDS the request runs the job
    itself instead of leaving it queued forever."""
    import app.tasks

    settings.JOB_PICKUP_SECONDS = 0
    monkeypatch.setattr(app.tasks, "enqueue", lambda task, *args, **kwargs: None)

    res = api_client.post(
        FUELS_URL + "bulk-upload/",
        {"file": SimpleUploadedFile("f.csv", _csv("fuel_type\nPetrol\n").getvalue(), content_type="text/csv")},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    assert res.json()["success_count"] == 1
    assert Fuel.objects.filter(fuel_type="Petrol").exists()


def test_job_runs_immediately_when_no_worker_is_running(api_client, settings, monkeypatch):
    """No live worker: the job is not queued and runs in the request at
    once, without waiting JOB_PICKUP_SECONDS."""
    import time

    import app.tasks
    from app.services import background_jobs

    settings.JOB_PICKUP_SECONDS = 60
    monkeypatch.setattr(background_jobs, "workers_available", lambda: False)

    def must_not_queue(*args, **kwargs):
        raise AssertionError("queued with no worker running")

    monkeypatch.setattr(app.tasks, "enqueue", must_not_queue)

    started = time.monotonic()
    res = api_client.post(
        FUELS_URL + "bulk-upload/",
        {"file": SimpleUploadedFile("f.csv", _csv("fuel_type\nPetrol\n").getvalue(), content_type="text/csv")},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    assert res.json()["success_count"] == 1
    assert time.monotonic() - started < 5
