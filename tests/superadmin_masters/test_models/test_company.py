"""Unit tests for Company model — CRUD + constraints."""
import pytest
from app.models.superadmin_masters.company import Company


@pytest.mark.django_db
class TestCompanyCreate:
    def test_basic_create(self):
        c = Company.objects.create(name="ACME Corp")
        assert c.name == "ACME Corp"

    def test_unique_id_prefix(self):
        c = Company.objects.create(name="Prefix Co")
        assert c.unique_id.startswith("CMP-")

    def test_str(self):
        c = Company.objects.create(name="Beta Ltd")
        assert str(c) == "Beta Ltd"

    def test_description_optional(self):
        c = Company.objects.create(name="Silent Corp")
        assert c.description is None

    def test_unique_ids_differ(self):
        c1 = Company.objects.create(name="Co1")
        c2 = Company.objects.create(name="Co2")
        assert c1.unique_id != c2.unique_id


@pytest.mark.django_db
class TestCompanyDefaults:
    def test_is_active_default_true(self):
        c = Company.objects.create(name="Active Co")
        assert c.is_active is True

    def test_is_deleted_default_false(self):
        c = Company.objects.create(name="Not Deleted")
        assert c.is_deleted is False

    def test_ordering_alphabetical(self):
        Company.objects.create(name="Zebra Inc")
        Company.objects.create(name="Apple LLC")
        names = list(Company.objects.values_list("name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestCompanySoftDelete:
    def test_soft_delete_sets_is_deleted(self):
        c = Company.objects.create(name="Delete Me")
        c.delete()
        c.refresh_from_db()
        assert c.is_deleted is True

    def test_soft_delete_sets_is_active_false(self):
        c = Company.objects.create(name="Deactivate Me")
        c.delete()
        c.refresh_from_db()
        assert c.is_active is False

    def test_record_still_in_db_after_soft_delete(self):
        c = Company.objects.create(name="Still Here")
        pk = c.unique_id
        c.delete()
        assert Company.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestCompanyUpdate:
    def test_update_name(self):
        c = Company.objects.create(name="Old Name")
        c.name = "New Name"
        c.save()
        c.refresh_from_db()
        assert c.name == "New Name"

    def test_update_description(self):
        c = Company.objects.create(name="Desc Corp")
        c.description = "Updated description"
        c.save()
        c.refresh_from_db()
        assert c.description == "Updated description"
