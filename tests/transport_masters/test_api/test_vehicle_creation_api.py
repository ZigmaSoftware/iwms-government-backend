"""API tests for VehicleCreation endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/transport-masters/vehicle-creation/"


@pytest.mark.django_db
class TestVehicleCreationAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestVehicleCreationAPICreate:
    def test_create_returns_success(self, auth_client, company, project):
        resp = auth_client.post(
            BASE,
            {
                "company_id_input": company.unique_id,
                "project_id_input": project.unique_id,
                "vehicle_no": "TN-01-AB-1234",
                "vehicle_condition": "NEW",
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestVehicleCreationAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, company, project):
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        v = VehicleCreation.objects.create(
            company_id=company, project_id=project,
            vehicle_no="TN-02-CD-5678",
        )
        resp = auth_client.get(f"{BASE}{v.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestVehicleCreationAPIUpdate:
    def test_patch_returns_success(self, auth_client, company, project):
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        v = VehicleCreation.objects.create(
            company_id=company, project_id=project,
            vehicle_no="TN-03-EF-9012",
        )
        resp = auth_client.patch(
            f"{BASE}{v.unique_id}/", {"vehicle_condition": "SECOND_HAND"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestVehicleCreationAPIDelete:
    def test_delete_returns_success(self, auth_client, company, project):
        from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
        v = VehicleCreation.objects.create(
            company_id=company, project_id=project,
            vehicle_no="TN-04-GH-3456",
        )
        resp = auth_client.delete(f"{BASE}{v.unique_id}/")
        assert resp.status_code in (200, 204)
