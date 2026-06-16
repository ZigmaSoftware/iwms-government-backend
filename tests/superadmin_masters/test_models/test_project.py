"""Unit tests for Project model — CRUD + constraints."""
import pytest
from app.models.superadmin_masters.project import Project


@pytest.mark.django_db
class TestProjectCreate:
    def test_basic_create(self, company):
        p = Project.objects.create(name="Main Project", company_id=company)
        assert p.name == "Main Project"

    def test_unique_id_prefix(self, company):
        p = Project.objects.create(name="Prefix Project", company_id=company)
        assert p.unique_id.startswith("PROJ-")

    def test_str(self, company):
        p = Project.objects.create(name="My Project", company_id=company)
        assert "My Project" in str(p)

    def test_foreign_key_company(self, project, company):
        assert project.company_id == company

    def test_unique_ids_differ(self, company):
        p1 = Project.objects.create(name="P1", company_id=company)
        p2 = Project.objects.create(name="P2", company_id=company)
        assert p1.unique_id != p2.unique_id


@pytest.mark.django_db
class TestProjectDefaults:
    def test_is_active_default_true(self, project):
        assert project.is_active is True

    def test_is_deleted_default_false(self, project):
        assert project.is_deleted is False


@pytest.mark.django_db
class TestProjectSoftDelete:
    def test_soft_delete_sets_is_deleted(self, project):
        project.delete()
        project.refresh_from_db()
        assert project.is_deleted is True

    def test_record_still_in_db_after_soft_delete(self, project):
        pk = project.unique_id
        project.delete()
        assert Project.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestProjectUpdate:
    def test_update_name(self, project):
        project.name = "Updated Project"
        project.save()
        project.refresh_from_db()
        assert project.name == "Updated Project"
