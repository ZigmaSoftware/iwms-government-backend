"""Single bulk-upload mechanism (BulkUploadMixin) — response contract.

Every module uploads the same way: CSV -> POST <resource>/bulk-upload/
-> {message, success_count, error_count, total_count, errors[]}.
"""
import io

import jwt
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
    res = api_client.post(
        FUELS_URL + "bulk-upload/",
        {"file": ("fuels.csv", _csv("fuel_type,description\nDiesel,for trucks\n,Diesel without name\n"), "text/csv")},
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
