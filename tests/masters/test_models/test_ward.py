"""Unit tests for Ward model — CRUD + constraints."""
import pytest
from app.models.masters.ward import Ward


@pytest.mark.django_db
class TestWardCreate:
    def test_basic_create(self, state, district, corporation):
        w = Ward.objects.create(
            ward_name="Ward Alpha",
            state=state,
            district=district,
            area_type=corporation.area_type_id,
            corporation=corporation,
        )
        assert w.ward_name == "Ward Alpha"

    def test_unique_id_prefix(self, ward):
        assert ward.unique_id.startswith("WARD-")

    def test_foreign_key_corporation(self, ward, corporation):
        assert ward.corporation_id == corporation.pk


@pytest.mark.django_db
class TestWardDefaults:
    def test_is_active_default_true(self, ward):
        assert ward.is_active is True

    def test_is_deleted_default_false(self, ward):
        assert ward.is_deleted is False

    def test_coordinates_default_empty_list(self, ward):
        assert ward.coordinates == []


@pytest.mark.django_db
class TestWardSoftDelete:
    def test_soft_delete(self, ward):
        ward.delete()
        ward.refresh_from_db()
        assert ward.is_deleted is True


@pytest.mark.django_db
class TestWardUpdate:
    def test_update_ward_name(self, ward):
        ward.ward_name = "Renamed Ward"
        ward.save()
        ward.refresh_from_db()
        assert ward.ward_name == "Renamed Ward"

    def test_update_coordinates(self, ward):
        ward.coordinates = [
            {"latitude": 13.0808, "longitude": 80.2731},
            {"latitude": 13.0832, "longitude": 80.2775},
            {"latitude": 13.0796, "longitude": 80.2801},
        ]
        ward.save()
        ward.refresh_from_db()
        assert len(ward.coordinates) == 3
