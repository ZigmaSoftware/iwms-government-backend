"""Unit tests for MainCategory grievance model — CRUD + constraints."""
import pytest
from django.db import IntegrityError
from app.models.grivences.main_category_citizenGrievance import MainCategory


@pytest.mark.django_db
class TestMainCategoryCreate:
    def test_basic_create(self):
        mc = MainCategory.objects.create(main_categoryName="Road Issue")
        assert mc.main_categoryName == "Road Issue"

    def test_unique_id_prefix(self):
        mc = MainCategory.objects.create(main_categoryName="Water Issue")
        assert mc.unique_id.startswith("CMPMC-")

    def test_str(self):
        mc = MainCategory.objects.create(main_categoryName="Sanitation")
        assert str(mc) == "Sanitation"

    def test_name_unique(self):
        MainCategory.objects.create(main_categoryName="DupCategory")
        with pytest.raises(IntegrityError):
            MainCategory.objects.create(main_categoryName="DupCategory")


@pytest.mark.django_db
class TestMainCategoryDefaults:
    def test_is_active_default_true(self):
        mc = MainCategory.objects.create(main_categoryName="Default Active")
        assert mc.is_active is True

    def test_is_deleted_default_false(self):
        mc = MainCategory.objects.create(main_categoryName="Not Deleted")
        assert mc.is_deleted is False


@pytest.mark.django_db
class TestMainCategorySoftDelete:
    def test_soft_delete(self):
        mc = MainCategory.objects.create(main_categoryName="Waste Issue")
        mc.delete()
        mc.refresh_from_db()
        assert mc.is_deleted is True
        assert mc.is_active is False


@pytest.mark.django_db
class TestMainCategoryUpdate:
    def test_update_name(self):
        mc = MainCategory.objects.create(main_categoryName="Old Name")
        mc.main_categoryName = "New Category"
        mc.save()
        mc.refresh_from_db()
        assert mc.main_categoryName == "New Category"
