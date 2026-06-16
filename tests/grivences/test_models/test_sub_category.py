"""Unit tests for SubCategory grievance model — CRUD + constraints."""
import pytest
from app.models.grivences.main_category_citizenGrievance import MainCategory
from app.models.grivences.sub_category_citizenGrievance import SubCategory


@pytest.fixture
def main_cat(db):
    return MainCategory.objects.create(main_categoryName="General Issues")


@pytest.mark.django_db
class TestSubCategoryCreate:
    def test_basic_create(self, main_cat):
        sc = SubCategory.objects.create(name="Missed Pickup", mainCategory=main_cat)
        assert sc.name == "Missed Pickup"

    def test_unique_id_prefix(self, main_cat):
        sc = SubCategory.objects.create(name="Late Collection", mainCategory=main_cat)
        assert sc.unique_id.startswith("CMPSC-")

    def test_str_contains_name(self, main_cat):
        sc = SubCategory.objects.create(name="Bin Full", mainCategory=main_cat)
        assert "Bin Full" in str(sc)

    def test_foreign_key_main_category(self, main_cat):
        sc = SubCategory.objects.create(name="Spillage", mainCategory=main_cat)
        assert sc.mainCategory == main_cat


@pytest.mark.django_db
class TestSubCategoryDefaults:
    def test_is_active_default_true(self, main_cat):
        sc = SubCategory.objects.create(name="Active Sub", mainCategory=main_cat)
        assert sc.is_active is True

    def test_is_deleted_default_false(self, main_cat):
        sc = SubCategory.objects.create(name="Not Deleted", mainCategory=main_cat)
        assert sc.is_deleted is False


@pytest.mark.django_db
class TestSubCategorySoftDelete:
    def test_soft_delete(self, main_cat):
        sc = SubCategory.objects.create(name="Broken Bin", mainCategory=main_cat)
        sc.delete()
        sc.refresh_from_db()
        assert sc.is_deleted is True
        assert sc.is_active is False


@pytest.mark.django_db
class TestSubCategoryUpdate:
    def test_update_name(self, main_cat):
        sc = SubCategory.objects.create(name="Old Name", mainCategory=main_cat)
        sc.name = "Updated Name"
        sc.save()
        sc.refresh_from_db()
        assert sc.name == "Updated Name"
