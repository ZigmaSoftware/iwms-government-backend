"""Unit tests for UserScreen model — CRUD + constraints."""
import pytest
from app.models.superadmin.screen_management.mainscreentype import MainScreenType
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen


@pytest.fixture
def main_screen(db):
    mst = MainScreenType.objects.create(type_name="Masters")
    return MainScreen.objects.create(mainscreen_name="masters", mainscreentype_id=mst, order_no=1)


@pytest.mark.django_db
class TestUserScreenCreate:
    def test_basic_create(self, main_screen):
        us = UserScreen.objects.create(userscreen_name="states", mainscreen_id=main_screen, folder_name="masters", order_no=1)
        assert us.userscreen_name == "states"

    def test_unique_id_prefix(self, main_screen):
        us = UserScreen.objects.create(userscreen_name="cities", mainscreen_id=main_screen, folder_name="masters", order_no=2)
        assert us.unique_id.startswith("USERSCREEN-")

    def test_foreign_key_mainscreen(self, main_screen):
        us = UserScreen.objects.create(userscreen_name="zones", mainscreen_id=main_screen, folder_name="masters", order_no=3)
        assert us.mainscreen_id == main_screen


@pytest.mark.django_db
class TestUserScreenDefaults:
    def test_is_active_default_true(self, main_screen):
        us = UserScreen.objects.create(userscreen_name="wards", mainscreen_id=main_screen, folder_name="masters", order_no=4)
        assert us.is_active is True

    def test_is_deleted_default_false(self, main_screen):
        us = UserScreen.objects.create(userscreen_name="areas", mainscreen_id=main_screen, folder_name="masters", order_no=5)
        assert us.is_deleted is False


@pytest.mark.django_db
class TestUserScreenSoftDelete:
    def test_soft_delete(self, main_screen):
        us = UserScreen.objects.create(userscreen_name="temp", mainscreen_id=main_screen, folder_name="masters", order_no=6)
        us.delete()
        us.refresh_from_db()
        assert us.is_deleted is True


@pytest.mark.django_db
class TestUserScreenUpdate:
    def test_update_name(self, main_screen):
        us = UserScreen.objects.create(userscreen_name="old", mainscreen_id=main_screen, folder_name="masters", order_no=7)
        us.userscreen_name = "new"
        us.save()
        us.refresh_from_db()
        assert us.userscreen_name == "new"
