"""API tests for UserType endpoint — CRUD operations."""
import jwt
import pytest
from django.conf import settings

BASE = "/api/v1/role-assigns/user-type/"


def _staff_auth_client(api_client, company, project, user_type):
    from app.models.user_creations.staffcreation import Staffcreation

    staff = Staffcreation.objects.create(
        employee_name="Company Admin",
        username="company_admin",
        password="x",
        user_type_id=user_type,
        company_id=company,
        project_id=project,
        login_enabled=True,
    )
    token = jwt.encode(
        {
            "unique_id": staff.staff_unique_id,
            "permissions": {
                "role-assigns": {
                    "user-type": ["view"],
                },
            },
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.mark.django_db
class TestUserTypeAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client, user_type):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200

    def test_company_staff_can_list_global_user_types(
        self,
        api_client,
        company,
        project,
        user_type,
    ):
        client = _staff_auth_client(api_client, company, project, user_type)

        resp = client.get(BASE)

        assert resp.status_code == 200
        assert any(item["unique_id"] == user_type.unique_id for item in resp.data)


@pytest.mark.django_db
class TestUserTypeAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(BASE, {"name": "Manager"}, format="json")
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestUserTypeAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, user_type):
        resp = auth_client.get(f"{BASE}{user_type.unique_id}/")
        assert resp.status_code == 200

    def test_retrieve_returns_correct_name(self, auth_client, user_type):
        resp = auth_client.get(f"{BASE}{user_type.unique_id}/")
        assert resp.json().get("name") == user_type.name


@pytest.mark.django_db
class TestUserTypeAPIUpdate:
    def test_patch_returns_success(self, auth_client, user_type):
        resp = auth_client.patch(f"{BASE}{user_type.unique_id}/", {"name": "Senior Staff"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestUserTypeAPIDelete:
    def test_delete_returns_success(self, auth_client, user_type):
        resp = auth_client.delete(f"{BASE}{user_type.unique_id}/")
        assert resp.status_code in (200, 204)
