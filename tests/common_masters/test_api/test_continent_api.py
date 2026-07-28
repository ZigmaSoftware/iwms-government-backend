"""API tests for Continent endpoint — CRUD operations."""
import pytest
from app.models.superadmin.common_masters.continent import Continent

BASE = "/api/v1/common-masters/continents/"


@pytest.mark.django_db
class TestContinentAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client, continent):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200

    def test_list_contains_created_continent(self, auth_client, continent):
        resp = auth_client.get(BASE)
        data = resp.json()
        items = data if isinstance(data, list) else data.get("results", data.get("data", []))
        names = [i.get("name") for i in items]
        assert continent.name in names


@pytest.mark.django_db
class TestContinentAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(BASE, {"name": "NewCont"}, format="json")
        assert resp.status_code in (200, 201)

    def test_create_persists_to_db(self, auth_client):
        auth_client.post(BASE, {"name": "PersistCont"}, format="json")
        assert Continent.objects.filter(name="PersistCont").exists()


@pytest.mark.django_db
class TestContinentAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, continent):
        resp = auth_client.get(f"{BASE}{continent.unique_id}/")
        assert resp.status_code == 200

    def test_retrieve_returns_correct_name(self, auth_client, continent):
        resp = auth_client.get(f"{BASE}{continent.unique_id}/")
        assert resp.json().get("name") == continent.name


@pytest.mark.django_db
class TestContinentAPIUpdate:
    def test_patch_returns_success(self, auth_client, continent):
        resp = auth_client.patch(f"{BASE}{continent.unique_id}/", {"name": "Updated"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestContinentAPIDelete:
    def test_delete_returns_success(self, auth_client, continent):
        resp = auth_client.delete(f"{BASE}{continent.unique_id}/")
        assert resp.status_code in (200, 204)
