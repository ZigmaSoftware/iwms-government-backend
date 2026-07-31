"""Historical import compatibility for the Staff Management rename."""

from app.models.superadmin.staff_management.unassigned_staff_pool import (  # noqa: F401
    UnassignedStaffPool,
    generate_unassigned_staff_pool_id,
)

__all__ = ["UnassignedStaffPool", "generate_unassigned_staff_pool_id"]
