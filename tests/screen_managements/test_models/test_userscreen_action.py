"""Unit tests for UserScreenAction model — CRUD + constraints."""
import pytest
from app.models.screen_managements.userscreenaction import UserScreenAction


@pytest.mark.django_db
class TestUserScreenActionCreate:
    def test_basic_create(self):
        a = UserScreenAction.objects.create(action_name="export", variable_name="can_export")
        assert a.action_name == "export"
        assert a.variable_name == "can_export"

    def test_unique_id_prefix(self):
        a = UserScreenAction.objects.create(action_name="import", variable_name="can_import")
        assert a.unique_id.startswith("USERSCRNACT-")

    def test_str_contains_name(self):
        a = UserScreenAction.objects.create(action_name="print", variable_name="can_print")
        assert "print" in str(a)


@pytest.mark.django_db
class TestUserScreenActionDefaults:
    def test_is_active_default_true(self):
        a = UserScreenAction.objects.create(action_name="download", variable_name="can_download")
        assert a.is_active is True

    def test_is_deleted_default_false(self):
        a = UserScreenAction.objects.create(action_name="upload", variable_name="can_upload")
        assert a.is_deleted is False


@pytest.mark.django_db
class TestUserScreenActionSoftDelete:
    def test_soft_delete(self):
        a = UserScreenAction.objects.create(action_name="temp", variable_name="temp_var")
        a.delete()
        a.refresh_from_db()
        assert a.is_deleted is True


@pytest.mark.django_db
class TestUserScreenActionUpdate:
    def test_update_action_name(self):
        a = UserScreenAction.objects.create(action_name="old_action", variable_name="old_var")
        a.action_name = "new_action"
        a.save()
        a.refresh_from_db()
        assert a.action_name == "new_action"
