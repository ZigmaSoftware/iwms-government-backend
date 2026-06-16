"""Unit tests for StaffUserType model — CRUD + constraints."""
import pytest
from app.models.role_assigns.staffUserType import StaffUserType


@pytest.mark.django_db
class TestStaffUserTypeCreate:
    def test_basic_create(self, user_type):
        s = StaffUserType.objects.create(name="driver", usertype_id=user_type)
        assert s.name == "driver"

    def test_unique_id_prefix(self, user_type):
        s = StaffUserType.objects.create(name="operator", usertype_id=user_type)
        assert s.unique_id.startswith("STUSRTYPE-")

    def test_str_contains_name(self, user_type):
        s = StaffUserType.objects.create(name="supervisor", usertype_id=user_type)
        assert "supervisor" in str(s)

    def test_foreign_key_usertype(self, user_type):
        s = StaffUserType.objects.create(name="checker", usertype_id=user_type)
        assert s.usertype_id == user_type


@pytest.mark.django_db
class TestStaffUserTypeDefaults:
    def test_is_active_default_true(self, user_type):
        s = StaffUserType.objects.create(name="helper", usertype_id=user_type)
        assert s.is_active is True

    def test_is_deleted_default_false(self, user_type):
        s = StaffUserType.objects.create(name="loader", usertype_id=user_type)
        assert s.is_deleted is False


@pytest.mark.django_db
class TestStaffUserTypeSoftDelete:
    def test_soft_delete(self, user_type):
        s = StaffUserType.objects.create(name="temp_type", usertype_id=user_type)
        s.delete()
        s.refresh_from_db()
        assert s.is_deleted is True
        assert s.is_active is False


@pytest.mark.django_db
class TestStaffUserTypeUpdate:
    def test_update_name(self, user_type):
        s = StaffUserType.objects.create(name="old_name", usertype_id=user_type)
        s.name = "new_name"
        s.save()
        s.refresh_from_db()
        assert s.name == "new_name"
