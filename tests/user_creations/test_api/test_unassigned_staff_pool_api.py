"""API tests for UnassignedStaffPool endpoint."""
import pytest

BASE = "/api/v1/user-creations/unassigned-staff-pool/"


@pytest.mark.django_db
class TestUnassignedStaffPoolAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestUnassignedStaffPoolAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}USP-NOTEXIST/")
        assert resp.status_code in (404, 400)
