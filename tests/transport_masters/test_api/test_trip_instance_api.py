"""API tests for TripInstance endpoint."""
import pytest

BASE = "/api/v1/transport-masters/trip-instance/"


@pytest.mark.django_db
class TestTripInstanceAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestTripInstanceAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}TRIPINST-NOTEXIST/")
        assert resp.status_code in (404, 400)
