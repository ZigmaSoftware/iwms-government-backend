"""Unit tests for Property model — CRUD + constraints."""
import pytest
from app.models.masters.waste_masters.property import Property


@pytest.mark.django_db
class TestPropertyCreate:
    def test_basic_create(self):
        p = Property.objects.create(property_name="Residential")
        assert p.property_name == "Residential"

    def test_unique_id_prefix(self):
        p = Property.objects.create(property_name="Commercial")
        assert p.unique_id.startswith("PROPERTY-")

    def test_str_contains_name(self):
        p = Property.objects.create(property_name="Industrial")
        assert "Industrial" in str(p)

    def test_unique_ids_differ(self):
        p1 = Property.objects.create(property_name="Prop1")
        p2 = Property.objects.create(property_name="Prop2")
        assert p1.unique_id != p2.unique_id


@pytest.mark.django_db
class TestPropertyDefaults:
    def test_is_active_default_true(self):
        p = Property.objects.create(property_name="Hospital")
        assert p.is_active is True

    def test_is_deleted_default_false(self):
        p = Property.objects.create(property_name="School")
        assert p.is_deleted is False


@pytest.mark.django_db
class TestPropertySoftDelete:
    def test_soft_delete(self):
        p = Property.objects.create(property_name="Temp")
        p.delete()
        p.refresh_from_db()
        assert p.is_deleted is True


@pytest.mark.django_db
class TestPropertyUpdate:
    def test_update_name(self):
        p = Property.objects.create(property_name="Old Name")
        p.property_name = "New Name"
        p.save()
        p.refresh_from_db()
        assert p.property_name == "New Name"
