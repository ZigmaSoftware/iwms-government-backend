"""Unit tests for StaffcreationOfficeDetails model — CRUD + constraints."""
import pytest
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


@pytest.fixture
def staff(db, company, project):
    return StaffcreationOfficeDetails.objects.create(
        employee_name="John Driver",
        company_id=company,
        project_id=project,
    )


@pytest.mark.django_db
class TestStaffCreationCreate:
    def test_basic_create(self, staff):
        assert staff.employee_name == "John Driver"

    def test_unique_id_prefix(self, staff):
        assert staff.staff_unique_id.startswith("STC-")

    def test_str_contains_name(self, staff):
        assert "John Driver" in str(staff)

    def test_emp_id_auto_generated(self, staff):
        assert staff.emp_id is not None
        assert len(staff.emp_id) > 0

    def test_foreign_key_company(self, staff, company):
        assert staff.company_id == company

    def test_unique_ids_differ(self, staff, company, project):
        s2 = StaffcreationOfficeDetails.objects.create(
            employee_name="Jane Operator",
            company_id=company,
            project_id=project,
        )
        assert staff.staff_unique_id != s2.staff_unique_id


@pytest.mark.django_db
class TestStaffCreationDefaults:
    def test_is_active_default_true(self, staff):
        assert staff.is_active is True

    def test_is_deleted_default_false(self, staff):
        assert staff.is_deleted is False

    def test_optional_fields_nullable(self, staff):
        assert staff.department is None
        assert staff.designation is None
        assert staff.office_email is None


@pytest.mark.django_db
class TestStaffCreationSoftDelete:
    def test_soft_delete(self, staff):
        staff.delete()
        staff.refresh_from_db()
        assert staff.is_deleted is True
        assert staff.is_active is False


@pytest.mark.django_db
class TestStaffCreationUpdate:
    def test_update_employee_name(self, staff):
        staff.employee_name = "Updated Name"
        staff.save()
        staff.refresh_from_db()
        assert staff.employee_name == "Updated Name"
