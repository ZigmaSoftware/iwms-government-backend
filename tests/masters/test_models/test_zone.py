"""Unit tests for Zone model — CRUD + constraints."""
import pytest
from decimal import Decimal
from app.models.masters.zone import Zone


@pytest.mark.django_db
class TestZoneCreate:
    def test_basic_create(self, state, district, city):
        z = Zone.objects.create(zone_name="Zone Alpha", state_id=state, district_id=district, city_id=city)
        assert z.zone_name == "Zone Alpha"

    def test_unique_id_prefix(self, zone):
        assert zone.unique_id.startswith("ZONE-")

    def test_foreign_keys(self, zone, state, district, city):
        assert zone.state_id == state
        assert zone.district_id == district
        assert zone.city_id == city


@pytest.mark.django_db
class TestZoneDefaults:
    def test_is_active_default_true(self, zone):
        assert zone.is_active is True

    def test_is_deleted_default_false(self, zone):
        assert zone.is_deleted is False

    def test_optional_geo_fields_null(self, state, district, city):
        z = Zone.objects.create(zone_name="Zone Beta", state_id=state, district_id=district, city_id=city)
        assert z.latitude is None
        assert z.longitude is None
        assert z.coordinates == []

    def test_timestamps_set_on_create(self, zone):
        assert zone.created_at is not None
        assert zone.updated_at is not None


@pytest.mark.django_db
class TestZoneSoftDelete:
    def test_soft_delete(self, zone):
        zone.delete()
        zone.refresh_from_db()
        assert zone.is_deleted is True


@pytest.mark.django_db
class TestZoneUpdate:
    def test_update_zone_name(self, zone):
        zone.zone_name = "Renamed Zone"
        zone.save()
        zone.refresh_from_db()
        assert zone.zone_name == "Renamed Zone"

    def test_update_geo_coordinates(self, zone):
        zone.latitude = "12.9716"
        zone.longitude = "77.5946"
        zone.coordinates = [
            {"latitude": 12.9716, "longitude": 77.5946},
            {"latitude": 12.9721, "longitude": 77.5991},
            {"latitude": 12.9684, "longitude": 77.6012},
        ]
        zone.save()
        zone.refresh_from_db()
        assert zone.latitude == Decimal("12.9716")
        assert len(zone.coordinates) == 3
        assert zone.coordinates[0]["latitude"] == 12.9716
