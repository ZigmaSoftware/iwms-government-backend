"""Unit tests for Collection_point model — CRUD + constraints."""
import pytest
from django.core.exceptions import ValidationError
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.masters.panchayat import Panchayat


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="CP Panchayat",
        company_id=company, project_id=project,
        state_id=state, district_id=district, city_id=city,
    )


@pytest.fixture
def cp_panchayat(db, company, project, state, district, city, panchayat):
    return Collection_point.objects.create(
        cp_name="Collection Point A",
        company_id=company, project_id=project,
        state_id=state, city_id=city, district_id=district,
        panchayat_id=panchayat,
        latitude="13.0827", longitude="80.2707",
    )


@pytest.fixture
def cp_ward(db, company, project, state, district, city, ward):
    return Collection_point.objects.create(
        cp_name="Collection Point B",
        company_id=company, project_id=project,
        state_id=state, city_id=city, district_id=district,
        ward_id=ward,
        latitude="13.0900", longitude="80.2800",
    )


@pytest.mark.django_db
class TestCollectionPointCreate:
    def test_create_with_panchayat(self, cp_panchayat):
        assert cp_panchayat.cp_name == "Collection Point A"

    def test_create_with_ward(self, cp_ward):
        assert cp_ward.cp_name == "Collection Point B"

    def test_unique_id_prefix(self, cp_panchayat):
        assert cp_panchayat.unique_id.startswith("CP-")

    def test_str_contains_name(self, cp_panchayat):
        assert "Collection Point A" in str(cp_panchayat)

    def test_neither_panchayat_nor_ward_raises(self, company, project, state, district, city):
        cp = Collection_point(
            cp_name="Bad CP",
            company_id=company, project_id=project,
            state_id=state, city_id=city, district_id=district,
            latitude="13.0", longitude="80.0",
        )
        with pytest.raises(ValidationError):
            cp.full_clean()


@pytest.mark.django_db
class TestCollectionPointDefaults:
    def test_is_active_default_true(self, cp_panchayat):
        assert cp_panchayat.is_active is True

    def test_is_deleted_default_false(self, cp_panchayat):
        assert cp_panchayat.is_deleted is False


@pytest.mark.django_db
class TestCollectionPointSoftDelete:
    def test_soft_delete(self, cp_panchayat):
        cp_panchayat.delete()
        cp_panchayat.refresh_from_db()
        assert cp_panchayat.is_deleted is True


@pytest.mark.django_db
class TestCollectionPointUpdate:
    def test_update_name(self, cp_panchayat):
        cp_panchayat.cp_name = "Updated CP"
        cp_panchayat.save()
        cp_panchayat.refresh_from_db()
        assert cp_panchayat.cp_name == "Updated CP"
