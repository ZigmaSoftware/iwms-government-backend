"""Unit tests for Designation model — CRUD + constraints."""
import pytest
from app.models.masters.designation import Designation
from app.models.masters.department import Department


@pytest.fixture
def department(db, company, project):
    return Department.objects.create(
        department_name="Engineering",
        department_code="ENG",
        company_id=company,
        project_id=project,
    )


@pytest.fixture
def designation(db, company, project, department):
    return Designation.objects.create(
        designation_name="Senior Engineer",
        department_id=department,
        company_id=company,
        project_id=project,
    )


@pytest.mark.django_db
class TestDesignationCreate:
    def test_basic_create(self, company, project, department):
        d = Designation.objects.create(
            designation_name="Junior Engineer",
            department_id=department,
            company_id=company,
            project_id=project,
        )
        assert d.designation_name == "Junior Engineer"

    def test_unique_id_prefix(self, designation):
        assert designation.unique_id.startswith("DESG-")

    def test_str(self, designation):
        assert str(designation) == "Senior Engineer"

    def test_foreign_key_department(self, designation, department):
        assert designation.department_id == department


@pytest.mark.django_db
class TestDesignationDefaults:
    def test_is_active_default_true(self, designation):
        assert designation.is_active is True

    def test_is_deleted_default_false(self, designation):
        assert designation.is_deleted is False

    def test_description_optional(self, designation):
        assert designation.description is None

    def test_ordering_alphabetical(self, company, project, department):
        Designation.objects.create(designation_name="Team Lead", department_id=department, company_id=company, project_id=project)
        Designation.objects.create(designation_name="Analyst", department_id=department, company_id=company, project_id=project)
        names = list(Designation.objects.values_list("designation_name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestDesignationSoftDelete:
    def test_soft_delete(self, designation):
        designation.delete()
        designation.refresh_from_db()
        assert designation.is_deleted is True


@pytest.mark.django_db
class TestDesignationUpdate:
    def test_update_name(self, designation):
        designation.designation_name = "Principal Engineer"
        designation.save()
        designation.refresh_from_db()
        assert designation.designation_name == "Principal Engineer"
