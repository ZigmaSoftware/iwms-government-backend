"""API tests for MainScreen and MainScreenType endpoints — CRUD operations."""
import pytest
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.mainscreen import MainScreen

SCREEN_TYPE_BASE = "/api/v1/screen-managements/mainscreentype/"
MAIN_SCREEN_BASE = "/api/v1/screen-managements/mainscreens/"


@pytest.mark.django_db
class TestMainScreenTypeAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(SCREEN_TYPE_BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        MainScreenType.objects.create(type_name="Masters")
        resp = auth_client.get(SCREEN_TYPE_BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestMainScreenTypeAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(SCREEN_TYPE_BASE, {"type_name": "Reports"}, format="json")
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestMainScreenAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(MAIN_SCREEN_BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        mst = MainScreenType.objects.create(type_name="Admin")
        MainScreen.objects.create(mainscreen_name="admin", mainscreentype_id=mst, order_no=1)
        resp = auth_client.get(MAIN_SCREEN_BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestMainScreenAPICreate:
    def test_create_returns_success(self, auth_client):
        mst = MainScreenType.objects.create(type_name="Transport")
        resp = auth_client.post(
            MAIN_SCREEN_BASE,
            {"mainscreen_name": "transport", "mainscreentype_id": mst.unique_id, "order_no": 1},
            format="json",
        )
        assert resp.status_code in (200, 201)
