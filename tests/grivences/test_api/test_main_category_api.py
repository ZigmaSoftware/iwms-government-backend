"""API tests for MainCategory grievance endpoint — CRUD operations."""
import pytest
from app.models.grivences.main_category_citizenGrievance import MainCategory

BASE = "/api/v1/grivences/main-category/"


@pytest.mark.django_db
class TestMainCategoryAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        MainCategory.objects.create(main_categoryName="Road")
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestMainCategoryAPICreate:
    def test_create_returns_success(self, auth_client):
        resp = auth_client.post(BASE, {"main_categoryName": "Electricity"}, format="json")
        assert resp.status_code in (200, 201)

    def test_create_persists_to_db(self, auth_client):
        auth_client.post(BASE, {"main_categoryName": "Water Supply"}, format="json")
        assert MainCategory.objects.filter(main_categoryName="Water Supply").exists()


@pytest.mark.django_db
class TestMainCategoryAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client):
        mc = MainCategory.objects.create(main_categoryName="Sewage")
        resp = auth_client.get(f"{BASE}{mc.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestMainCategoryAPIUpdate:
    def test_patch_returns_success(self, auth_client):
        mc = MainCategory.objects.create(main_categoryName="Drainage")
        resp = auth_client.patch(f"{BASE}{mc.unique_id}/", {"main_categoryName": "Updated"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestMainCategoryAPIDelete:
    def test_delete_returns_success(self, auth_client):
        mc = MainCategory.objects.create(main_categoryName="Temp Cat")
        resp = auth_client.delete(f"{BASE}{mc.unique_id}/")
        assert resp.status_code in (200, 204)
