"""API tests for AreaType endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/masters/areatypes/"


@pytest.mark.django_db
class TestAreaTypeAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestAreaTypeAPICreate:
    def test_create_returns_success(self, auth_client, state, city, district):
        resp = auth_client.post(
            BASE,
            {
                "name": "Rural",
                "state_id": state.unique_id,
                "city_id": city.unique_id,
                "district_id": district.unique_id,
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestAreaTypeAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, state, city, district):
        from app.models.masters.areatype import AreaType
        at = AreaType.objects.create(
            name="Urban", state_id=state, city_id=city, district_id=district
        )
        resp = auth_client.get(f"{BASE}{at.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestAreaTypeAPIUpdate:
    def test_patch_returns_success(self, auth_client, state, city, district):
        from app.models.masters.areatype import AreaType
        at = AreaType.objects.create(
            name="Semi-Urban", state_id=state, city_id=city, district_id=district
        )
        resp = auth_client.patch(
            f"{BASE}{at.unique_id}/", {"name": "Peri-Urban"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestAreaTypeAPIDelete:
    def test_delete_returns_success(self, auth_client, state, city, district):
        from app.models.masters.areatype import AreaType
        at = AreaType.objects.create(
            name="Coastal", state_id=state, city_id=city, district_id=district
        )
        resp = auth_client.delete(f"{BASE}{at.unique_id}/")
        assert resp.status_code in (200, 204)
