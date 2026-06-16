"""API tests for SubCategory grievance endpoint — CRUD operations."""
import pytest
from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.models.grivences.sub_category_citizenGrievance import SubCategory

BASE = "/api/v1/grivences/sub-category/"


@pytest.fixture
def main_cat(db):
    return MainCategory.objects.create(main_categoryName="Collection Issues")


@pytest.mark.django_db
class TestSubCategoryAPIList:
    def test_list_authenticated_returns_200(self, auth_client, main_cat):
        SubCategory.objects.create(name="Overflow", mainCategory=main_cat)
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestSubCategoryAPICreate:
    def test_create_returns_success(self, auth_client, main_cat):
        resp = auth_client.post(
            BASE,
            {"name": "Late Pickup", "mainCategory": main_cat.unique_id},
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestSubCategoryAPIRetrieve:
    def test_retrieve_returns_200(self, auth_client, main_cat):
        sc = SubCategory.objects.create(name="Broken Bin", mainCategory=main_cat)
        resp = auth_client.get(f"{BASE}{sc.unique_id}/")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestSubCategoryAPIUpdate:
    def test_patch_returns_success(self, auth_client, main_cat):
        sc = SubCategory.objects.create(name="Old Name", mainCategory=main_cat)
        resp = auth_client.patch(f"{BASE}{sc.unique_id}/", {"name": "Updated"}, format="json")
        assert resp.status_code in (200, 204)


@pytest.mark.django_db
class TestSubCategoryAPIDelete:
    def test_delete_returns_success(self, auth_client, main_cat):
        sc = SubCategory.objects.create(name="Temp Sub", mainCategory=main_cat)
        resp = auth_client.delete(f"{BASE}{sc.unique_id}/")
        assert resp.status_code in (200, 204)
