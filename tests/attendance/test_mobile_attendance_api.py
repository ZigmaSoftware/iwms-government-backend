import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from app.models.superadmin.user_management.attendance import Employee
from app.models.superadmin.user_management.staffcreation import Staffcreation


def _image(name="selfie.jpg"):
    return SimpleUploadedFile(name, b"fake image bytes", content_type="image/jpeg")


@pytest.mark.django_db
def test_staff_profile_is_mobile_readable_without_token(api_client):
    staff = Staffcreation.objects.create(
        employee_name="Driver User",
        username="driver.mobile",
        department="Sanitation",
        designation="Driver",
    )

    resp = api_client.get(
        "/api/v1/staff-profile/",
        {"staff_id_id": staff.staff_unique_id},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@pytest.mark.django_db
def test_register_updates_existing_attendance_selfie(api_client):
    staff = Staffcreation.objects.create(
        employee_name="Driver User",
        username="driver.register",
        department="Sanitation",
    )

    first = api_client.post(
        "/api/v1/register/",
        {
            "emp_id": staff.staff_unique_id,
            "name": "Driver User",
            "department": "Sanitation",
            "source_image": _image("first.jpg"),
        },
        format="multipart",
    )
    assert first.status_code == 200
    assert first.json()["message"] == "Employee registered successfully"

    second = api_client.post(
        "/api/v1/register/",
        {
            "emp_id": staff.staff_unique_id,
            "name": "Driver User Updated",
            "department": "Collection",
            "source_image": _image("second.jpg"),
        },
        format="multipart",
    )

    assert second.status_code == 200
    assert second.json()["message"] == "Employee registration updated successfully"
    assert Employee.objects.filter(staff=staff).count() == 1

    employee = Employee.objects.get(staff=staff)
    assert employee.name == "Driver User Updated"
    assert employee.department == "Collection"
    assert employee.image_path.startswith("emp_image/")
