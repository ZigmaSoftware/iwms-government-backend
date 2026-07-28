"""API tests for UserScreen endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/screen-managements/userscreens/"


@pytest.fixture
def main_screen(db):
    from app.models.superadmin.screen_management.mainscreentype import MainScreenType
    from app.models.superadmin.screen_management.mainscreen import MainScreen
    mst = MainScreenType.objects.create(type_name="Admin")
    return MainScreen.objects.create(
        mainscreen_name="Dashboard", mainscreentype_id=mst,
        icon_name="home", order_no=1,
    )


@pytest.mark.django_db
class TestUserScreenAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestUserScreenAPICreate:
    def test_create_returns_success(self, auth_client, main_screen):
        resp = auth_client.post(
            BASE,
            {
                "mainscreen_id": main_screen.unique_id,
                "userscreen_name": "Overview",
                "folder_name": "overview",
                "icon_name": "chart",
                "order_no": 1,
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestUserScreenAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}US-NOTEXIST/")
        assert resp.status_code in (404, 400)


@pytest.mark.django_db
class TestUserScreenAPIUpdate:
    def test_patch_returns_success(self, auth_client, main_screen):
        from app.models.superadmin.screen_management.userscreen import UserScreen
        us = UserScreen.objects.create(
            mainscreen_id=main_screen, userscreen_name="Monthly",
            folder_name="monthly", icon_name="calendar", order_no=1,
        )
        resp = auth_client.patch(
            f"{BASE}{us.unique_id}/", {"userscreen_name": "Annual"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestUserScreenAPIDelete:
    def test_delete_returns_success(self, auth_client, main_screen):
        from app.models.superadmin.screen_management.userscreen import UserScreen
        us = UserScreen.objects.create(
            mainscreen_id=main_screen, userscreen_name="Profile",
            folder_name="profile", icon_name="user", order_no=2,
        )
        resp = auth_client.delete(f"{BASE}{us.unique_id}/")
        assert resp.status_code in (200, 204)
