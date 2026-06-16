"""Unit tests for District model — CRUD + constraints."""
import pytest
from django.db import IntegrityError
from app.models.masters.district import District


@pytest.mark.django_db
class TestDistrictCreate:
    def test_basic_create(self, continent, country, state):
        d = District.objects.create(name="Coimbatore", continent_id=continent, country_id=country, state_id=state)
        assert d.name == "Coimbatore"

    def test_unique_id_prefix(self, district):
        assert district.unique_id.startswith("DIST-")

    def test_str_contains_name(self, district):
        assert "Chennai" in str(district)

    def test_foreign_key_state(self, district, state):
        assert district.state_id == state


@pytest.mark.django_db
class TestDistrictDefaults:
    def test_is_active_default_true(self, district):
        assert district.is_active is True

    def test_is_deleted_default_false(self, district):
        assert district.is_deleted is False

    def test_created_by_optional(self, district):
        assert district.created_by is None


@pytest.mark.django_db
class TestDistrictConstraints:
    def test_unique_together_state_name(self, continent, country, state):
        District.objects.create(name="Tiruchi", continent_id=continent, country_id=country, state_id=state)
        with pytest.raises(IntegrityError):
            District.objects.create(name="Tiruchi", continent_id=continent, country_id=country, state_id=state)


@pytest.mark.django_db
class TestDistrictSoftDelete:
    def test_soft_delete(self, district):
        district.delete()
        district.refresh_from_db()
        assert district.is_deleted is True


@pytest.mark.django_db
class TestDistrictUpdate:
    def test_update_name(self, district):
        district.name = "Renamed District"
        district.save()
        district.refresh_from_db()
        assert district.name == "Renamed District"
