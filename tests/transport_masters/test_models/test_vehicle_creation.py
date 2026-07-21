"""Unit tests for VehicleCreation model — CRUD + constraints."""
import pytest
from app.models.masters.transport_masters.fuel import Fuel
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation


@pytest.fixture
def fuel(db):
    return Fuel.objects.create(fuel_type="Diesel")


@pytest.fixture
def vehicle_type(db, company, project):
    return VehicleTypeCreation.objects.create(vehicleType="Compactor", company_id=company, project_id=project)


@pytest.fixture
def vehicle(db, company, project, fuel, vehicle_type):
    return VehicleCreation.objects.create(
        vehicle_no="TN01AB1234",
        fuel_type=fuel,
        vehicle_type=vehicle_type,
        capacity=10,
        company_id=company,
        project_id=project,
    )


@pytest.mark.django_db
class TestVehicleCreationCreate:
    def test_basic_create(self, vehicle):
        assert vehicle.vehicle_no == "TN01AB1234"
        assert vehicle.capacity == 10

    def test_unique_id_prefix(self, vehicle):
        assert vehicle.unique_id.startswith("VEHCRE-")

    def test_foreign_key_fuel(self, vehicle, fuel):
        assert vehicle.fuel_type == fuel

    def test_foreign_key_vehicle_type(self, vehicle, vehicle_type):
        assert vehicle.vehicle_type == vehicle_type

    def test_foreign_key_company(self, vehicle, company):
        assert vehicle.company_id == company


@pytest.mark.django_db
class TestVehicleCreationDefaults:
    def test_is_active_default_true(self, vehicle):
        assert vehicle.is_active is True

    def test_is_deleted_default_false(self, vehicle):
        assert vehicle.is_deleted is False


@pytest.mark.django_db
class TestVehicleCreationSoftDelete:
    def test_soft_delete(self, vehicle):
        vehicle.delete()
        vehicle.refresh_from_db()
        assert vehicle.is_deleted is True


@pytest.mark.django_db
class TestVehicleCreationUpdate:
    def test_update_vehicle_no(self, vehicle):
        vehicle.vehicle_no = "TN02XY9999"
        vehicle.save()
        vehicle.refresh_from_db()
        assert vehicle.vehicle_no == "TN02XY9999"

    def test_update_capacity(self, vehicle):
        vehicle.capacity = 20
        vehicle.save()
        vehicle.refresh_from_db()
        assert vehicle.capacity == 20
