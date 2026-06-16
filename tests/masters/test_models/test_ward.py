"""Unit tests for Ward model — CRUD + constraints."""
import pytest
from app.models.masters.ward import Ward


@pytest.mark.django_db
class TestWardCreate:
    def test_basic_create(self, state, district, city, zone):
        w = Ward.objects.create(ward_name="Ward Alpha", state_id=state, district_id=district, city_id=city, zone_id=zone)
        assert w.ward_name == "Ward Alpha"

    def test_unique_id_prefix(self, ward):
        assert ward.unique_id.startswith("WARD-")

    def test_foreign_key_zone(self, ward, zone):
        assert ward.zone_id == zone


@pytest.mark.django_db
class TestWardDefaults:
    def test_is_active_default_true(self, ward):
        assert ward.is_active is True

    def test_is_deleted_default_false(self, ward):
        assert ward.is_deleted is False


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
