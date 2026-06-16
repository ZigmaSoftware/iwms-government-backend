"""Unit tests for Department model — CRUD + constraints."""
import pytest
from django.db import IntegrityError
from app.models.masters.department import Department


@pytest.fixture
def department(db, company, project):
    return Department.objects.create(
        department_name="Engineering",
        department_code="ENG",
        company_id=company,
        project_id=project,
    )


@pytest.mark.django_db
class TestDepartmentCreate:
    def test_basic_create(self, company, project):
        d = Department.objects.create(
            department_name="Finance",
            department_code="FIN",
            company_id=company,
            project_id=project,
        )
        assert d.department_name == "Finance"
        assert d.department_code == "FIN"

    def test_unique_id_prefix(self, department):
        assert department.unique_id.startswith("DEPT-")

    def test_str(self, department):
        assert str(department) == "Engineering"

    def test_foreign_key_company(self, department, company):
        assert department.company_id == company


@pytest.mark.django_db
class TestDepartmentDefaults:
    def test_is_active_default_true(self, department):
        assert department.is_active is True

    def test_is_deleted_default_false(self, department):
        assert department.is_deleted is False

    def test_description_optional(self, department):
        assert department.description is None

    def test_ordering_alphabetical(self, company, project):
        Department.objects.create(department_name="Zoology", department_code="ZOO", company_id=company, project_id=project)
        Department.objects.create(department_name="Accounts", department_code="ACC", company_id=company, project_id=project)
        names = list(Department.objects.values_list("department_name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestDepartmentConstraints:
    def test_unique_code_per_project(self, company, project):
        Department.objects.create(department_name="HR", department_code="HR01", company_id=company, project_id=project)
        with pytest.raises(IntegrityError):
            Department.objects.create(department_name="Human Resources", department_code="HR01", company_id=company, project_id=project)


@pytest.mark.django_db
class TestDepartmentSoftDelete:
    def test_soft_delete(self, department):
        department.delete()
        department.refresh_from_db()
        assert department.is_deleted is True


@pytest.mark.django_db
class TestDepartmentUpdate:
    def test_update_name(self, department):
        department.department_name = "Updated Dept"
        department.save()
        department.refresh_from_db()
        assert department.department_name == "Updated Dept"
