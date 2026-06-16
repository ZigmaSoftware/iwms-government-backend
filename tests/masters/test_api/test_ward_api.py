"""API tests for Ward endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/masters/wards/"


@pytest.mark.django_db
class TestWardAPIList:
    def test_list_authenticated_returns_200(self, auth_client, ward):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWardAPICreate:
    def test_create_returns_success(self, auth_client, state, district, city, zone):
        resp = auth_client.post(
            BASE,
            {"ward_name": "New Ward", "state_id": state.unique_id,
             "district_id": district.unique_id, "city_id": city.unique_id,
             "zone_id": zone.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestWardAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, ward):
        resp = auth_client.get(f"{BASE}{ward.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWardAPIUpdate:
    def test_patch_returns_success(self, auth_client, ward):
        resp = auth_client.patch(f"{BASE}{ward.unique_id}/", {"ward_name": "Updated Ward"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestWardAPIDelete:
    def test_delete_returns_success(self, auth_client, ward):
        resp = auth_client.delete(f"{BASE}{ward.unique_id}/")
        assert resp.status_code in (200, 204)
