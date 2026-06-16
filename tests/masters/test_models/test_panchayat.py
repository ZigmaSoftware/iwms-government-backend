"""Unit tests for Panchayat model — CRUD + constraints."""
import pytest
from app.models.masters.panchayat import Panchayat


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Test Panchayat",
        company_id=company,
        project_id=project,
        state_id=state,
        district_id=district,
        city_id=city,
    )


@pytest.mark.django_db
class TestPanchayatCreate:
    def test_basic_create(self, company, project, state, district, city):
        p = Panchayat.objects.create(
            panchayat_name="Village Council",
            company_id=company,
            project_id=project,
            state_id=state,
            district_id=district,
            city_id=city,
        )
        assert p.panchayat_name == "Village Council"

    def test_unique_id_prefix(self, panchayat):
        assert panchayat.unique_id.startswith("PANCHAYAT-")

    def test_foreign_key_city(self, panchayat, city):
        assert panchayat.city_id == city

    def test_foreign_key_state(self, panchayat, state):
        assert panchayat.state_id == state


@pytest.mark.django_db
class TestPanchayatDefaults:
    def test_is_active_default_true(self, panchayat):
        assert panchayat.is_active is True

    def test_is_deleted_default_false(self, panchayat):
        assert panchayat.is_deleted is False

    def test_optional_geo_fields_null(self, panchayat):
        assert panchayat.latitude is None
        assert panchayat.longitude is None

    def test_agreed_weight_defaults(self, panchayat):
        assert panchayat.agreed_weight_kg == 0
        assert panchayat.weight_unit == "kg"
        assert panchayat.effective_from is None


@pytest.mark.django_db
class TestPanchayatSoftDelete:
    def test_soft_delete(self, panchayat):
        panchayat.delete()
        panchayat.refresh_from_db()
        assert panchayat.is_deleted is True


@pytest.mark.django_db
class TestPanchayatUpdate:
    def test_update_name(self, panchayat):
        panchayat.panchayat_name = "Updated Panchayat"
        panchayat.save()
        panchayat.refresh_from_db()
        assert panchayat.panchayat_name == "Updated Panchayat"

    def test_update_agreed_weight(self, panchayat):
        panchayat.agreed_weight_kg = "1250.50"
        panchayat.weight_unit = "tonne"
        panchayat.effective_from = "2026-05-01"
        panchayat.save()
        panchayat.refresh_from_db()
        assert str(panchayat.agreed_weight_kg) == "1250.50"
        assert panchayat.weight_unit == "tonne"
        assert str(panchayat.effective_from) == "2026-05-01"
