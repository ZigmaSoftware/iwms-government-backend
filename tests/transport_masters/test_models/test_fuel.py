"""Unit tests for Fuel model — CRUD + constraints."""
import pytest
from app.models.transport_masters.fuel import Fuel


@pytest.mark.django_db
class TestFuelCreate:
    def test_basic_create(self):
        f = Fuel.objects.create(fuel_type="Diesel")
        assert f.fuel_type == "Diesel"

    def test_unique_id_prefix(self):
        f = Fuel.objects.create(fuel_type="Petrol")
        assert f.unique_id.startswith("FUEL-")

    def test_str(self):
        f = Fuel.objects.create(fuel_type="CNG")
        assert str(f) == "CNG"

    def test_description_optional(self):
        f = Fuel.objects.create(fuel_type="Hydrogen")
        assert f.description is None


@pytest.mark.django_db
class TestFuelDefaults:
    def test_is_active_default_true(self):
        f = Fuel.objects.create(fuel_type="Electric")
        assert f.is_active is True

    def test_is_deleted_default_false(self):
        f = Fuel.objects.create(fuel_type="LPG")
        assert f.is_deleted is False

    def test_ordering_alphabetical(self):
        Fuel.objects.create(fuel_type="Zebra Gas")
        Fuel.objects.create(fuel_type="Alpha Gas")
        names = list(Fuel.objects.values_list("fuel_type", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestFuelSoftDelete:
    def test_soft_delete(self):
        f = Fuel.objects.create(fuel_type="SolarFuel")
        f.delete()
        f.refresh_from_db()
        assert f.is_deleted is True
        assert f.is_active is False


@pytest.mark.django_db
class TestFuelUpdate:
    def test_update_fuel_type(self):
        f = Fuel.objects.create(fuel_type="Old Type")
        f.fuel_type = "New Type"
        f.save()
        f.refresh_from_db()
        assert f.fuel_type == "New Type"

    def test_update_description(self):
        f = Fuel.objects.create(fuel_type="Bio Fuel")
        f.description = "Bio diesel blend"
        f.save()
        f.refresh_from_db()
        assert f.description == "Bio diesel blend"
