"""Unit tests for User (auth_user) model — CRUD + constraints."""
import pytest
from app.models.superadmin_masters.auth_user import User


@pytest.mark.django_db
class TestUserCreate:
    def test_create_superuser(self):
        u = User.objects.create_superuser(username="admin1", password="pass1234")
        assert u.username == "admin1"

    def test_superuser_unique_id_prefix(self):
        u = User.objects.create_superuser(username="admin2", password="pass1234")
        assert u.unique_id.startswith("SUPUSER-")

    def test_superuser_is_superuser_true(self):
        u = User.objects.create_superuser(username="admin3", password="pass1234")
        assert u.is_superuser is True

    def test_str_returns_username(self):
        u = User.objects.create_superuser(username="display_user", password="pass")
        assert str(u) == "display_user"

    def test_non_superuser_without_company_raises(self):
        with pytest.raises(ValueError, match="must belong to a company"):
            User.objects.create_user(username="nocompany", password="pass")


@pytest.mark.django_db
class TestUserDefaults:
    def test_is_active_default_true(self):
        u = User.objects.create_superuser(username="flag_test", password="pass")
        assert u.is_active is True

    def test_is_deleted_default_false(self):
        u = User.objects.create_superuser(username="del_test", password="pass")
        assert u.is_deleted is False

    def test_superuser_has_no_company(self):
        u = User.objects.create_superuser(username="pure_platform", password="pass")
        assert u.company_id is None
        assert u.project_id is None


@pytest.mark.django_db
class TestUserSecurity:
    def test_password_is_hashed(self):
        u = User.objects.create_superuser(username="hashtest", password="plaintext")
        assert u.password != "plaintext"
        assert u.check_password("plaintext") is True

    def test_unique_ids_differ(self):
        u1 = User.objects.create_superuser(username="user_a", password="pass")
        u2 = User.objects.create_superuser(username="user_b", password="pass")
        assert u1.unique_id != u2.unique_id
