"""API tests for VehicleType endpoint — CRUD operations."""
import pytest
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation

BASE = "/api/v1/transport-masters/vehicle-type/"


@pytest.mark.django_db
class TestVehicleTypeAPIList:
    def test_list_authenticated_returns_200(self, auth_client, company, project):
        VehicleTypeCreation.objects.create(vehicleType="Compactor", company_id=company, project_id=project)
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestVehicleTypeAPICreate:
    def test_create_returns_success(self, auth_client, company, project):
        resp = auth_client.post(
            BASE,
            {"vehicleType": "Tipper", "company_id_input": company.unique_id, "project_id_input": project.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestVehicleTypeAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Loader", company_id=company, project_id=project)
        resp = auth_client.get(f"{BASE}{vt.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestVehicleTypeAPIUpdate:
    def test_patch_returns_success(self, auth_client, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Dumper", company_id=company, project_id=project)
        resp = auth_client.patch(f"{BASE}{vt.unique_id}/", {"vehicleType": "Updated"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestVehicleTypeAPIDelete:
    def test_delete_returns_success(self, auth_client, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="TempType", company_id=company, project_id=project)
        resp = auth_client.delete(f"{BASE}{vt.unique_id}/")
        assert resp.status_code in (200, 204)
