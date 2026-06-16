"""API tests for Designation endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/masters/designations/"


@pytest.mark.django_db
class TestDesignationAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDesignationAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(
            BASE,
            {"designation_name": "Field Officer"},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestDesignationAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}DESG-NOTEXIST/")
        assert resp.status_code in (404, 400)


@pytest.mark.django_db
class TestDesignationAPIUpdate:
    def test_patch_returns_success(self, auth_client):
        from app.models.masters.designation import Designation
        desg = Designation.objects.create(designation_name="Supervisor")
        resp = auth_client.patch(
            f"{BASE}{desg.unique_id}/", {"designation_name": "Senior Supervisor"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestDesignationAPIDelete:
    def test_delete_returns_success(self, auth_client):
        from app.models.masters.designation import Designation
        desg = Designation.objects.create(designation_name="Temp Officer")
        resp = auth_client.delete(f"{BASE}{desg.unique_id}/")
        assert resp.status_code in (200, 204)
