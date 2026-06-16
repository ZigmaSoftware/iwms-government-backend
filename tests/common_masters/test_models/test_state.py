"""Unit tests for State (common_masters) model — CRUD + constraints."""
import pytest
from app.models.common_masters.state import State


@pytest.mark.django_db
class TestStateCreate:
    def test_basic_create(self, continent, country):
        s = State.objects.create(name="Kerala", label="KL", continent_id=continent, country_id=country)
        assert s.name == "Kerala"
        assert s.label == "KL"

    def test_unique_id_prefix(self, continent, country):
        s = State.objects.create(name="Goa", label="GA", continent_id=continent, country_id=country)
        assert s.unique_id.startswith("STATE-")

    def test_str(self, state):
        assert "Tamil Nadu" in str(state)

    def test_foreign_keys(self, state, continent, country):
        assert state.continent_id == continent
        assert state.country_id == country


@pytest.mark.django_db
class TestStateDefaults:
    def test_is_active_default_true(self, continent, country):
        s = State.objects.create(name="Assam", label="AS", continent_id=continent, country_id=country)
        assert s.is_active is True

    def test_is_deleted_default_false(self, continent, country):
        s = State.objects.create(name="Bihar", label="BR", continent_id=continent, country_id=country)
        assert s.is_deleted is False


@pytest.mark.django_db
class TestStateSoftDelete:
    def test_soft_delete(self, state):
        state.delete()
        state.refresh_from_db()
        assert state.is_deleted is True


@pytest.mark.django_db
class TestStateUpdate:
    def test_update_name(self, state):
        state.name = "Updated State"
        state.save()
        state.refresh_from_db()
        assert state.name == "Updated State"

    def test_update_label(self, state):
        state.label = "XX"
        state.save()
        state.refresh_from_db()
        assert state.label == "XX"
