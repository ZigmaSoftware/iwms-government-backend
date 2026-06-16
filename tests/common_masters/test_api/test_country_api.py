"""API tests for Country endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/common-masters/countries/"


@pytest.mark.django_db
class TestCountryAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client, country):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestCountryAPICreate:
    def test_create_returns_success(self, auth_client, continent):
        resp = auth_client.post(
            BASE,
            {"name": "Brazil", "continent_id": continent.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestCountryAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, country):
        resp = auth_client.get(f"{BASE}{country.unique_id}/")
        assert resp.status_code == 200

    def test_retrieve_returns_correct_name(self, auth_client, country):
        resp = auth_client.get(f"{BASE}{country.unique_id}/")
        assert resp.json().get("name") == country.name


@pytest.mark.django_db
class TestCountryAPIUpdate:
    def test_patch_returns_success(self, auth_client, country):
        resp = auth_client.patch(f"{BASE}{country.unique_id}/", {"name": "Updated Country"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestCountryAPIDelete:
    def test_delete_returns_success(self, auth_client, country):
        resp = auth_client.delete(f"{BASE}{country.unique_id}/")
        assert resp.status_code in (200, 204)
