"""API tests for WasteType (bluetooth) endpoint."""
import pytest

BASE = "/api/v1/waste-bluetooth/types/"


@pytest.mark.django_db
class TestWasteBluetoothTypeAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWasteBluetoothTypeAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(
            BASE,
            {"waste_type_name": "Biomedical"},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestWasteBluetoothTypeAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}9999/")
        assert resp.status_code in (404, 400)
