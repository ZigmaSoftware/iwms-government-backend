"""Historical import compatibility for the Staff Management rename."""

from app.models.superadmin.staff_management.staff_data_scope import (  # noqa: F401
    StaffDataScope,
    generate_staff_data_scope_id,
)

__all__ = ["StaffDataScope", "generate_staff_data_scope_id"]
