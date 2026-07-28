"""Unit tests for Continent model — CRUD + constraints."""
import pytest
from app.models.superadmin.common_masters.continent import Continent


@pytest.mark.django_db
class TestContinentCreate:
    def test_basic_create(self):
        c = Continent.objects.create(name="Europe")
        assert c.name == "Europe"

    def test_unique_id_prefix(self):
        c = Continent.objects.create(name="Africa")
        assert c.unique_id.startswith("CONT-")

    def test_str(self):
        c = Continent.objects.create(name="Oceania")
        assert str(c) == "Oceania"

    def test_unique_id_is_primary_key(self):
        c = Continent.objects.create(name="Americas")
        assert Continent.objects.get(pk=c.unique_id) == c

    def test_unique_ids_differ(self):
        c1 = Continent.objects.create(name="C1")
        c2 = Continent.objects.create(name="C2")
        assert c1.unique_id != c2.unique_id


@pytest.mark.django_db
class TestContinentDefaults:
    def test_is_active_default_true(self):
        c = Continent.objects.create(name="Asia")
        assert c.is_active is True

    def test_is_deleted_default_false(self):
        c = Continent.objects.create(name="Antarctica")
        assert c.is_deleted is False

    def test_ordering_alphabetical(self):
        Continent.objects.create(name="Zzz Land")
        Continent.objects.create(name="Aaa Land")
        names = list(Continent.objects.values_list("name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestContinentSoftDelete:
    def test_soft_delete_sets_is_deleted(self):
        c = Continent.objects.create(name="Delete Me")
        c.delete()
        c.refresh_from_db()
        assert c.is_deleted is True

    def test_record_survives_soft_delete(self):
        c = Continent.objects.create(name="Survivor")
        pk = c.unique_id
        c.delete()
        assert Continent.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestContinentUpdate:
    def test_update_name(self):
        c = Continent.objects.create(name="Old Continent")
        c.name = "New Continent"
        c.save()
        c.refresh_from_db()
        assert c.name == "New Continent"
