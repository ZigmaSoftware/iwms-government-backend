"""API tests for District endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/masters/districts/"


@pytest.mark.django_db
class TestDistrictAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client, district):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDistrictAPICreate:
    def test_create_returns_success(self, auth_client, continent, country, state):
        resp = auth_client.post(
            BASE,
            {"name": "Madurai", "continent_id": continent.unique_id,
             "country_id": country.unique_id, "state_id": state.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestDistrictAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, district):
        resp = auth_client.get(f"{BASE}{district.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDistrictAPIUpdate:
    def test_patch_returns_success(self, auth_client, district):
        resp = auth_client.patch(f"{BASE}{district.unique_id}/", {"name": "Updated District"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestDistrictAPIDelete:
    def test_delete_returns_success(self, auth_client, district):
        resp = auth_client.delete(f"{BASE}{district.unique_id}/")
        assert resp.status_code in (200, 204)
