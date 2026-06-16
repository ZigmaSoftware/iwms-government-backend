"""Unit tests for AdministrativeHierarchy model — CRUD + constraints."""
import pytest
from app.models.masters.hierarchy import AdministrativeHierarchy


@pytest.fixture
def hierarchy(db, area_type):
    return AdministrativeHierarchy.objects.create(
        area_type=area_type,
        level_name="Zone",
    )


@pytest.mark.django_db
class TestHierarchyCreate:
    def test_basic_create(self, area_type):
        h = AdministrativeHierarchy.objects.create(area_type=area_type, level_name="Ward")
        assert h.level_name == "Ward"

    def test_unique_id_prefix(self, hierarchy):
        assert hierarchy.unique_id.startswith("HIER-")

    def test_hierarchy_order_auto_set(self, hierarchy):
        assert hierarchy.hierarchy_order is not None
        assert hierarchy.hierarchy_order >= 1

    def test_foreign_key_area_type(self, hierarchy, area_type):
        assert hierarchy.area_type == area_type


@pytest.mark.django_db
class TestHierarchyDefaults:
    def test_is_active_default_true(self, hierarchy):
        assert hierarchy.is_active is True

    def test_is_deleted_default_false(self, hierarchy):
        assert hierarchy.is_deleted is False


@pytest.mark.django_db
class TestHierarchySoftDelete:
    def test_soft_delete(self, hierarchy):
        hierarchy.delete()
        hierarchy.refresh_from_db()
        assert hierarchy.is_deleted is True


@pytest.mark.django_db
class TestHierarchyUpdate:
    def test_update_level_name(self, hierarchy):
        hierarchy.level_name = "Panchayat"
        hierarchy.save()
        hierarchy.refresh_from_db()
        assert hierarchy.level_name == "Panchayat"
