"""Unit tests for SubProperty model — CRUD + constraints."""
import pytest
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


@pytest.fixture
def prop(db):
    return Property.objects.create(property_name="Residential")


@pytest.mark.django_db
class TestSubPropertyCreate:
    def test_basic_create(self, prop):
        sp = SubProperty.objects.create(sub_property_name="Apartment", property_id=prop)
        assert sp.sub_property_name == "Apartment"

    def test_unique_id_prefix(self, prop):
        sp = SubProperty.objects.create(sub_property_name="Villa", property_id=prop)
        assert sp.unique_id.startswith("SUBPROPERTY-")

    def test_str_contains_name(self, prop):
        sp = SubProperty.objects.create(sub_property_name="Office", property_id=prop)
        assert "Office" in str(sp)

    def test_foreign_key_property(self, prop):
        sp = SubProperty.objects.create(sub_property_name="Mall", property_id=prop)
        assert sp.property_id == prop


@pytest.mark.django_db
class TestSubPropertyDefaults:
    def test_is_active_default_true(self, prop):
        sp = SubProperty.objects.create(sub_property_name="Factory", property_id=prop)
        assert sp.is_active is True

    def test_is_deleted_default_false(self, prop):
        sp = SubProperty.objects.create(sub_property_name="Warehouse", property_id=prop)
        assert sp.is_deleted is False


@pytest.mark.django_db
class TestSubPropertySoftDelete:
    def test_soft_delete(self, prop):
        sp = SubProperty.objects.create(sub_property_name="Temp", property_id=prop)
        sp.delete()
        sp.refresh_from_db()
        assert sp.is_deleted is True


@pytest.mark.django_db
class TestSubPropertyUpdate:
    def test_update_name(self, prop):
        sp = SubProperty.objects.create(sub_property_name="Old", property_id=prop)
        sp.sub_property_name = "New"
        sp.save()
        sp.refresh_from_db()
        assert sp.sub_property_name == "New"
