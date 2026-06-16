"""API tests for Department endpoint — CRUD operations."""
import pytest
from app.models.masters.department import Department

BASE = "/api/v1/masters/departments/"


@pytest.fixture
def department(db, company, project):
    return Department.objects.create(
        department_name="Engineering", department_code="ENG",
        company_id=company, project_id=project,
    )


@pytest.mark.django_db
class TestDepartmentAPIList:
    def test_list_authenticated_returns_200(self, auth_client, department):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDepartmentAPICreate:
    def test_create_returns_success(self, auth_client, company, project):
        resp = auth_client.post(
            BASE,
            {"department_name": "Finance", "department_code": "FIN",
             "company_id": company.unique_id, "project_id": project.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestDepartmentAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, department):
        resp = auth_client.get(f"{BASE}{department.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDepartmentAPIUpdate:
    def test_patch_returns_success(self, auth_client, department):
        resp = auth_client.patch(f"{BASE}{department.unique_id}/", {"department_name": "Updated Dept"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestDepartmentAPIDelete:
    def test_delete_returns_success(self, auth_client, department):
        resp = auth_client.delete(f"{BASE}{department.unique_id}/")
        assert resp.status_code in (200, 204)
