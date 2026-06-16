"""API tests for StaffUserType endpoint — CRUD operations."""
import pytest
from app.models.role_assigns.staffUserType import StaffUserType

BASE = "/api/v1/role-assigns/staffusertypes/"


@pytest.mark.django_db
class TestStaffUserTypeAPIList:
    def test_list_authenticated_returns_200(self, auth_client, user_type):
        StaffUserType.objects.create(name="driver", usertype_id=user_type)
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestStaffUserTypeAPICreate:
    def test_create_returns_success(self, auth_client, user_type):
        resp = auth_client.post(
            BASE,
            {"name": "company_operator", "usertype_id": user_type.pk},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestStaffUserTypeAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, user_type):
        sut = StaffUserType.objects.create(name="supervisor", usertype_id=user_type)
        resp = auth_client.get(f"{BASE}{sut.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestStaffUserTypeAPIUpdate:
    def test_patch_returns_success(self, auth_client, user_type):
        sut = StaffUserType.objects.create(name="company_driver", usertype_id=user_type)
        resp = auth_client.patch(f"{BASE}{sut.unique_id}/", {"name": "company_supervisor"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestStaffUserTypeAPIDelete:
    def test_delete_returns_success(self, auth_client, user_type):
        sut = StaffUserType.objects.create(name="temp_staff", usertype_id=user_type)
        resp = auth_client.delete(f"{BASE}{sut.unique_id}/")
        assert resp.status_code in (200, 204)
