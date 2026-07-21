"""Unit tests for Country model — CRUD + constraints."""
import pytest
from app.models.superadmin.common_masters.country import Country


@pytest.mark.django_db
class TestCountryCreate:
    def test_basic_create(self, continent):
        c = Country.objects.create(name="France", continent_id=continent, currency="EUR", mob_code="+33")
        assert c.name == "France"

    def test_unique_id_prefix(self, continent):
        c = Country.objects.create(name="Germany", continent_id=continent)
        assert c.unique_id.startswith("COUNTRY-")

    def test_str(self, continent):
        c = Country.objects.create(name="Spain", continent_id=continent)
        assert str(c) == "Spain"

    def test_foreign_key_continent(self, continent):
        c = Country.objects.create(name="Portugal", continent_id=continent)
        assert c.continent_id == continent


@pytest.mark.django_db
class TestCountryDefaults:
    def test_is_active_default_true(self, continent):
        c = Country.objects.create(name="Italy", continent_id=continent)
        assert c.is_active is True

    def test_is_deleted_default_false(self, continent):
        c = Country.objects.create(name="Greece", continent_id=continent)
        assert c.is_deleted is False

    def test_optional_fields_nullable(self, continent):
        c = Country.objects.create(name="Morocco", continent_id=continent)
        assert c.currency is None
        assert c.mob_code is None

    def test_ordering_alphabetical(self, continent):
        Country.objects.create(name="Zimbabwe", continent_id=continent)
        Country.objects.create(name="Albania", continent_id=continent)
        names = list(Country.objects.values_list("name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestCountrySoftDelete:
    def test_soft_delete_sets_is_deleted(self, continent):
        c = Country.objects.create(name="Temp Country", continent_id=continent)
        c.delete()
        c.refresh_from_db()
        assert c.is_deleted is True


@pytest.mark.django_db
class TestCountryUpdate:
    def test_update_name(self, country):
        country.name = "Updated Country"
        country.save()
        country.refresh_from_db()
        assert country.name == "Updated Country"

    def test_update_currency(self, country):
        country.currency = "USD"
        country.save()
        country.refresh_from_db()
        assert country.currency == "USD"
