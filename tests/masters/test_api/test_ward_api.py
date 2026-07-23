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
    def test_create_returns_success(self, auth_client, state, district, corporation):
        resp = auth_client.post(
            BASE,
            {
                "ward_name": "New Ward",
                "state_id": state.unique_id,
                "district_id": district.unique_id,
                "area_type_id": corporation.area_type_id.unique_id,
                "corporation_id": corporation.unique_id,
                "coordinates": [
                    {"latitude": 13.0808, "longitude": 80.2731},
                    {"latitude": 13.0832, "longitude": 80.2775},
                    {"latitude": 13.0796, "longitude": 80.2801},
                ],
            },
            format="json",
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert len(data["coordinates"]) == 3
        assert data["coordinates"][0]["longitude"] == 80.2731
        assert data["local_body_type"] == "corporation"

    def test_create_without_local_body_fails(self, auth_client, state, district):
        resp = auth_client.post(
            BASE,
            {"ward_name": "Orphan Ward", "state_id": state.unique_id, "district_id": district.unique_id},
            format="json",
        )
        assert resp.status_code == 400

    def test_create_with_two_local_bodies_fails(self, auth_client, corporation):
        resp = auth_client.post(
            BASE,
            {
                "ward_name": "Ambiguous Ward",
                "corporation_id": corporation.unique_id,
                "panchayat_id": corporation.unique_id,
            },
            format="json",
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestWardAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, ward):
        resp = auth_client.get(f"{BASE}{ward.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestWardAPIUpdate:
    def test_patch_returns_success(self, auth_client, ward):
        resp = auth_client.patch(
            f"{BASE}{ward.unique_id}/",
            {
                "ward_name": "Updated Ward",
                "coordinates": [
                    {"lat": 13.0701, "lng": 80.2601},
                    {"lat": 13.0751, "lng": 80.2641},
                    {"lat": 13.0711, "lng": 80.2681},
                ],
            },
            format="json",
        )
        assert resp.status_code in (200, 204)
        ward.refresh_from_db()
        assert len(ward.coordinates) == 3


@pytest.mark.django_db
class TestWardAPIDelete:
    def test_delete_returns_success(self, auth_client, ward):
        resp = auth_client.delete(f"{BASE}{ward.unique_id}/")
        assert resp.status_code in (200, 204)
