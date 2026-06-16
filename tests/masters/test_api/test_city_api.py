"""API tests for City endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/masters/cities/"


@pytest.mark.django_db
class TestCityAPIList:
    def test_list_authenticated_returns_200(self, auth_client, city):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestCityAPICreate:
    def test_create_returns_success(self, auth_client, company, project, continent, country, state, district):
        resp = auth_client.post(
            BASE,
            {
                "name": "Madurai City",
                "continent_id": continent.unique_id,
                "country_id": country.unique_id,
                "state_id": state.unique_id,
                "district_id": district.unique_id,
                "company_id": company.unique_id,
                "project_id": project.unique_id,
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestCityAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, city):
        resp = auth_client.get(f"{BASE}{city.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestCityAPIUpdate:
    def test_patch_returns_success(self, auth_client, city):
        resp = auth_client.patch(f"{BASE}{city.unique_id}/", {"name": "Updated City"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestCityAPIDelete:
    def test_delete_returns_success(self, auth_client, city):
        resp = auth_client.delete(f"{BASE}{city.unique_id}/")
        assert resp.status_code in (200, 204)
