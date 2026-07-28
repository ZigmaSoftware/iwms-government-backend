"""Unit tests for MainScreenType model — CRUD + constraints."""
import pytest
from app.models.superadmin.screen_management.mainscreentype import MainScreenType


@pytest.mark.django_db
class TestMainScreenTypeCreate:
    def test_basic_create(self):
        mst = MainScreenType.objects.create(type_name="Masters")
        assert mst.type_name == "Masters"

    def test_unique_id_prefix(self):
        mst = MainScreenType.objects.create(type_name="Reports")
        assert mst.unique_id.startswith("MSCRTYPE-")

    def test_str_contains_name(self):
        mst = MainScreenType.objects.create(type_name="Dashboard")
        assert "Dashboard" in str(mst)


@pytest.mark.django_db
class TestMainScreenTypeDefaults:
    def test_is_active_default_true(self):
        mst = MainScreenType.objects.create(type_name="Admin")
        assert mst.is_active is True

    def test_is_deleted_default_false(self):
        mst = MainScreenType.objects.create(type_name="Assets")
        assert mst.is_deleted is False


@pytest.mark.django_db
class TestMainScreenTypeSoftDelete:
    def test_soft_delete(self):
        mst = MainScreenType.objects.create(type_name="Temp")
        mst.delete()
        mst.refresh_from_db()
        assert mst.is_deleted is True


@pytest.mark.django_db
class TestMainScreenTypeUpdate:
    def test_update_type_name(self):
        mst = MainScreenType.objects.create(type_name="Old Type")
        mst.type_name = "New Type"
        mst.save()
        mst.refresh_from_db()
        assert mst.type_name == "New Type"
