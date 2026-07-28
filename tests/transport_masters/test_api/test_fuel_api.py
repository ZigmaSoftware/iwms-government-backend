"""API tests for Fuel endpoint — CRUD operations."""
import pytest
from app.models.masters.transport_masters.fuel import Fuel

BASE = "/api/v1/transport-masters/fuels/"


@pytest.mark.django_db
class TestFuelAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        Fuel.objects.create(fuel_type="Diesel")
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestFuelAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(BASE, {"fuel_type": "LPG"}, format="json")
        assert resp.status_code in (200, 201)

    def test_create_persists_to_db(self, auth_client):
        auth_client.post(BASE, {"fuel_type": "BioDiesel"}, format="json")
        assert Fuel.objects.filter(fuel_type="BioDiesel").exists()


@pytest.mark.django_db
class TestFuelAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client):
        fuel = Fuel.objects.create(fuel_type="CNG")
        resp = auth_client.get(f"{BASE}{fuel.unique_id}/")
        assert resp.status_code == 200

    def test_retrieve_returns_correct_type(self, auth_client):
        fuel = Fuel.objects.create(fuel_type="Electric")
        resp = auth_client.get(f"{BASE}{fuel.unique_id}/")
        assert resp.json().get("fuel_type") == "Electric"


@pytest.mark.django_db
class TestFuelAPIUpdate:
    def test_patch_returns_success(self, auth_client):
        fuel = Fuel.objects.create(fuel_type="Old Fuel")
        resp = auth_client.patch(f"{BASE}{fuel.unique_id}/", {"fuel_type": "EV"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestFuelAPIDelete:
    def test_delete_returns_success(self, auth_client):
        fuel = Fuel.objects.create(fuel_type="Hydrogen")
        resp = auth_client.delete(f"{BASE}{fuel.unique_id}/")
        assert resp.status_code in (200, 204)
