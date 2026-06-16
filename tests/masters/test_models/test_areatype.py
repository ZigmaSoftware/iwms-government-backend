"""Unit tests for AreaType model — CRUD + constraints."""
import pytest
from app.models.masters.areatype import AreaType


@pytest.mark.django_db
class TestAreaTypeCreate:
    def test_basic_create(self, state, district, city):
        a = AreaType.objects.create(name="Rural", state_id=state, district_id=district, city_id=city)
        assert a.name == "Rural"

    def test_str(self, state, district, city):
        a = AreaType.objects.create(name="Urban", state_id=state, district_id=district, city_id=city)
        assert str(a) == "Urban"


@pytest.mark.django_db
class TestAreaTypeDefaults:
    def test_is_active_default_true(self, area_type):
        assert area_type.is_active is True

    def test_is_deleted_default_false(self, area_type):
        assert area_type.is_deleted is False


@pytest.mark.django_db
class TestAreaTypeSoftDelete:
    def test_soft_delete(self, state, district, city):
        a = AreaType.objects.create(name="Coastal", state_id=state, district_id=district, city_id=city)
        a.delete()
        a.refresh_from_db()
        assert a.is_deleted is True


@pytest.mark.django_db
class TestAreaTypeUpdate:
    def test_update_name(self, area_type):
        area_type.name = "Semi-Urban"
        area_type.save()
        area_type.refresh_from_db()
        assert area_type.name == "Semi-Urban"
