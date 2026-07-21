"""Unit tests for VehicleTypeCreation model — CRUD + constraints."""
import pytest
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation


@pytest.mark.django_db
class TestVehicleTypeCreate:
    def test_basic_create(self, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Compactor", company_id=company, project_id=project)
        assert vt.vehicleType == "Compactor"

    def test_unique_id_prefix(self, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Tipper", company_id=company, project_id=project)
        assert vt.unique_id.startswith("VHTYPE-")

    def test_str_contains_type(self, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Dumper", company_id=company, project_id=project)
        assert "Dumper" in str(vt)

    def test_foreign_key_company(self, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Loader", company_id=company, project_id=project)
        assert vt.company_id == company


@pytest.mark.django_db
class TestVehicleTypeDefaults:
    def test_is_active_default_true(self, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Mini Truck", company_id=company, project_id=project)
        assert vt.is_active is True

    def test_is_deleted_default_false(self, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Autorickshaw", company_id=company, project_id=project)
        assert vt.is_deleted is False


@pytest.mark.django_db
class TestVehicleTypeSoftDelete:
    def test_soft_delete(self, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Temp Type", company_id=company, project_id=project)
        vt.delete()
        vt.refresh_from_db()
        assert vt.is_deleted is True


@pytest.mark.django_db
class TestVehicleTypeUpdate:
    def test_update_type(self, company, project):
        vt = VehicleTypeCreation.objects.create(vehicleType="Old Type", company_id=company, project_id=project)
        vt.vehicleType = "Updated Type"
        vt.save()
        vt.refresh_from_db()
        assert vt.vehicleType == "Updated Type"
