"""Unit tests for MainScreen model — CRUD + constraints."""
import pytest
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.mainscreen import MainScreen


@pytest.fixture
def screen_type(db):
    return MainScreenType.objects.create(type_name="Masters")


@pytest.mark.django_db
class TestMainScreenCreate:
    def test_basic_create(self, screen_type):
        ms = MainScreen.objects.create(mainscreen_name="common-masters", mainscreentype_id=screen_type, order_no=1)
        assert ms.mainscreen_name == "common-masters"

    def test_unique_id_prefix(self, screen_type):
        ms = MainScreen.objects.create(mainscreen_name="screen-mgmt", mainscreentype_id=screen_type, order_no=2)
        assert ms.unique_id.startswith("MAINSCREEN-")

    def test_str_contains_name(self, screen_type):
        ms = MainScreen.objects.create(mainscreen_name="transport", mainscreentype_id=screen_type, order_no=3)
        assert "transport" in str(ms)

    def test_foreign_key_screentype(self, screen_type):
        ms = MainScreen.objects.create(mainscreen_name="assets", mainscreentype_id=screen_type, order_no=4)
        assert ms.mainscreentype_id == screen_type


@pytest.mark.django_db
class TestMainScreenDefaults:
    def test_is_active_default_true(self, screen_type):
        ms = MainScreen.objects.create(mainscreen_name="test", mainscreentype_id=screen_type, order_no=5)
        assert ms.is_active is True

    def test_is_deleted_default_false(self, screen_type):
        ms = MainScreen.objects.create(mainscreen_name="test2", mainscreentype_id=screen_type, order_no=6)
        assert ms.is_deleted is False


@pytest.mark.django_db
class TestMainScreenSoftDelete:
    def test_soft_delete(self, screen_type):
        ms = MainScreen.objects.create(mainscreen_name="del-screen", mainscreentype_id=screen_type, order_no=7)
        ms.delete()
        ms.refresh_from_db()
        assert ms.is_deleted is True


@pytest.mark.django_db
class TestMainScreenUpdate:
    def test_update_name(self, screen_type):
        ms = MainScreen.objects.create(mainscreen_name="old-screen", mainscreentype_id=screen_type, order_no=8)
        ms.mainscreen_name = "new-screen"
        ms.save()
        ms.refresh_from_db()
        assert ms.mainscreen_name == "new-screen"
