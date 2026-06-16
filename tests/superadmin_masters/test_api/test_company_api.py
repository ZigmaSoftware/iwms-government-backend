"""API tests for Company endpoint — CRUD operations."""
import pytest
from app.models.superadmin_masters.company import Company

BASE = "/api/v1/superadmin/company/"


@pytest.mark.django_db
class TestCompanyAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client, company):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200

    def test_list_contains_created_company(self, auth_client, company):
        resp = auth_client.get(BASE)
        data = resp.json()
        items = data if isinstance(data, list) else data.get("results", data.get("data", []))
        names = [i.get("name") for i in items]
        assert company.name in names


@pytest.mark.django_db
class TestCompanyAPICreate:
    def test_create_returns_201(self, auth_client):
        resp = auth_client.post(BASE, {"name": "New Company"}, format="json")
        assert resp.status_code in (200, 201)

    def test_create_persists_to_db(self, auth_client):
        auth_client.post(BASE, {"name": "Persist Co"}, format="json")
        assert Company.objects.filter(name="Persist Co").exists()


@pytest.mark.django_db
class TestCompanyAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, company):
        resp = auth_client.get(f"{BASE}{company.unique_id}/")
        assert resp.status_code == 200

    def test_retrieve_returns_correct_name(self, auth_client, company):
        resp = auth_client.get(f"{BASE}{company.unique_id}/")
        assert resp.json().get("name") == company.name


@pytest.mark.django_db
class TestCompanyAPIUpdate:
    def test_patch_returns_success(self, auth_client, company):
        resp = auth_client.patch(
            f"{BASE}{company.unique_id}/", {"name": "Renamed"}, format="json"
        )
        assert resp.status_code in (200, 204)

    def test_patch_updates_db(self, auth_client, company):
        auth_client.patch(
            f"{BASE}{company.unique_id}/", {"name": "DB Updated"}, format="json"
        )
        company.refresh_from_db()
        assert company.name == "DB Updated"


@pytest.mark.django_db
class TestCompanyAPIDelete:
    def test_delete_returns_success(self, auth_client, company):
        resp = auth_client.delete(f"{BASE}{company.unique_id}/")
        assert resp.status_code in (200, 204)

    def test_delete_soft_deletes(self, auth_client, company):
        auth_client.delete(f"{BASE}{company.unique_id}/")
        company.refresh_from_db()
        assert company.is_deleted is True
