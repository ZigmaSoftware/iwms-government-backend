"""Unit tests for UserType model — CRUD + constraints."""
import pytest
from django.db import IntegrityError
from app.models.superadmin.role_management.userType import UserType


@pytest.mark.django_db
class TestUserTypeCreate:
    def test_basic_create(self):
        u = UserType.objects.create(name="Customer")
        assert u.name == "Customer"

    def test_unique_id_prefix(self):
        u = UserType.objects.create(name="Admin")
        assert u.unique_id.startswith("UTYPE-")

    def test_str(self):
        u = UserType.objects.create(name="Staff")
        assert str(u) == "Staff"

    def test_name_unique(self):
        UserType.objects.create(name="UniqueRole")
        with pytest.raises(IntegrityError):
            UserType.objects.create(name="UniqueRole")


@pytest.mark.django_db
class TestUserTypeDefaults:
    def test_is_active_default_true(self):
        u = UserType.objects.create(name="Manager")
        assert u.is_active is True

    def test_is_deleted_default_false(self):
        u = UserType.objects.create(name="Contractor")
        assert u.is_deleted is False

    def test_ordering_alphabetical(self):
        UserType.objects.create(name="Zebra Role")
        UserType.objects.create(name="Apple Role")
        names = list(UserType.objects.values_list("name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestUserTypeSoftDelete:
    def test_soft_delete(self):
        u = UserType.objects.create(name="Temp Type")
        u.delete()
        u.refresh_from_db()
        assert u.is_deleted is True
        assert u.is_active is False


@pytest.mark.django_db
class TestUserTypeUpdate:
    def test_update_name(self, user_type):
        user_type.name = "Updated Role"
        user_type.save()
        user_type.refresh_from_db()
        assert user_type.name == "Updated Role"
