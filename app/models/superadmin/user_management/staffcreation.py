"""Historical import compatibility for the Staff Management rename."""

from app.models.superadmin.staff_management.staffcreation import (  # noqa: F401
    StaffPersonalDetails,
    Staffcreation,
    StaffcreationOfficeDetails,
    generate_staff_unique_id,
)

__all__ = [
    "StaffPersonalDetails",
    "Staffcreation",
    "StaffcreationOfficeDetails",
    "generate_staff_unique_id",
]
