"""API tests for UserScreenAction endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/screen-managements/userscreen-action/"


@pytest.mark.django_db
class TestUserScreenActionAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestUserScreenActionAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(
            BASE,
            {"action_name": "View", "variable_name": "can_view"},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestUserScreenActionAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}USA-NOTEXIST/")
        assert resp.status_code in (404, 400)


@pytest.mark.django_db
class TestUserScreenActionAPIUpdate:
    def test_patch_returns_success(self, auth_client):
        from app.models.screen_managements.userscreenaction import UserScreenAction
        action = UserScreenAction.objects.create(action_name="Edit", variable_name="can_edit")
        resp = auth_client.patch(
            f"{BASE}{action.unique_id}/", {"action_name": "Modify"}, format="json"
        )
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestUserScreenActionAPIDelete:
    def test_delete_returns_success(self, auth_client):
        from app.models.screen_managements.userscreenaction import UserScreenAction
        action = UserScreenAction.objects.create(action_name="Delete", variable_name="can_delete")
        resp = auth_client.delete(f"{BASE}{action.unique_id}/")
        assert resp.status_code in (200, 204)
