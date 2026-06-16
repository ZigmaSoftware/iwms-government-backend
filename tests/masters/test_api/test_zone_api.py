"""API tests for Zone endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/masters/zones/"


@pytest.mark.django_db
class TestZoneAPIList:
    def test_list_authenticated_returns_200(self, auth_client, zone):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestZoneAPICreate:
    def test_create_returns_success(self, auth_client, state, district, city):
        resp = auth_client.post(
            BASE,
            {"zone_name": "New Zone", "state_id": state.unique_id,
             "district_id": district.unique_id, "city_id": city.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestZoneAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, zone):
        resp = auth_client.get(f"{BASE}{zone.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestZoneAPIUpdate:
    def test_patch_returns_success(self, auth_client, zone):
        resp = auth_client.patch(f"{BASE}{zone.unique_id}/", {"zone_name": "Updated Zone"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestZoneAPIDelete:
    def test_delete_returns_success(self, auth_client, zone):
        resp = auth_client.delete(f"{BASE}{zone.unique_id}/")
        assert resp.status_code in (200, 204)
