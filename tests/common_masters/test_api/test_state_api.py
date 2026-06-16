"""API tests for State endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/common-masters/states/"


@pytest.mark.django_db
class TestStateAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client, state):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestStateAPICreate:
    def test_create_returns_success(self, auth_client, country, continent):
        resp = auth_client.post(
            BASE,
            {
                "name": "New State",
                "country_id": country.unique_id,
                "continent_id": continent.unique_id,
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestStateAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, state):
        resp = auth_client.get(f"{BASE}{state.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestStateAPIUpdate:
    def test_patch_returns_success(self, auth_client, state):
        resp = auth_client.patch(
            f"{BASE}{state.unique_id}/", {"name": "Updated State"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestStateAPIDelete:
    def test_delete_returns_success(self, auth_client, state):
        resp = auth_client.delete(f"{BASE}{state.unique_id}/")
        assert resp.status_code in (200, 204)
