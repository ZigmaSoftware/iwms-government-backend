"""API tests for Property endpoint — CRUD operations."""
import pytest
from app.models.masters.waste_masters.property import Property

BASE = "/api/v1/waste-types/properties/"


@pytest.mark.django_db
class TestPropertyAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        Property.objects.create(property_name="Residential")
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPropertyAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(BASE, {"property_name": "Commercial"}, format="json")
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestPropertyAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client):
        p = Property.objects.create(property_name="Industrial")
        resp = auth_client.get(f"{BASE}{p.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestPropertyAPIUpdate:
    def test_patch_returns_success(self, auth_client):
        p = Property.objects.create(property_name="Hospital")
        resp = auth_client.patch(f"{BASE}{p.unique_id}/", {"property_name": "Updated"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestPropertyAPIDelete:
    def test_delete_returns_success(self, auth_client):
        p = Property.objects.create(property_name="School")
        resp = auth_client.delete(f"{BASE}{p.unique_id}/")
        assert resp.status_code in (200, 204)
