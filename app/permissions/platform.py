from rest_framework.permissions import BasePermission, SAFE_METHODS

from app.utils.roles import is_admin_role, is_supervisor_role


class PlatformSuperAdminOnly(BasePermission):
    """Allow only platform-level super admins."""

    message = "Platform super admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_superuser", False)
        )


class SuperAdminApprovalPermission(PlatformSuperAdminOnly):
    """Allow only platform super admins to change user login approval state."""

    message = "Only Super Admin can change user approval status"


class CompanyAdminOnly(BasePermission):
    """Allow non-superuser staff with an admin role (company or government)."""

    message = "Company admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and not getattr(user, "is_superuser", False)
            and is_admin_role(user)
        )


class PlatformOrCompanyAdminFullAccess(BasePermission):
    """Allow platform super admins or staff users with admin role."""

    message = "Platform super admin or company admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        is_platform_super_admin = bool(
            getattr(user, "is_superuser", False)
        )

        is_company_admin = bool(
            not getattr(user, "is_superuser", False)
            and is_admin_role(user)
        )

        return is_platform_super_admin or is_company_admin




class PlatformOrCompanyAdminOnly(BasePermission):
    """
    Allow:
    - Platform super admin → full access
    - Staff admin → read-only access
    """

    message = "Platform super admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return False

        # ✅ Platform Super Admin → Full Access
        is_platform_super_admin = bool(
            getattr(user, "is_superuser", False)
        )

        if is_platform_super_admin:
            return True

        # ✅ Company / government admin
        is_company_admin = bool(
            not getattr(user, "is_superuser", False)
            and is_admin_role(user)
        )

        if is_company_admin:
            # 🔒 Allow only SAFE methods (GET, HEAD, OPTIONS)
            return request.method in SAFE_METHODS

        return False


class ScheduleModuleWriteAccess(BasePermission):
    """Allow write access to schedule / daily-trip screens for a platform super
    admin, any admin (company or government), or any supervisor (company or
    government, e.g. ``govt_corporation_supervisor``). Read is open to any
    authenticated user; per-screen limits are still enforced by the module
    permission middleware / UserScreenPermission rows."""

    message = "Schedule module write access requires an admin or supervisor role"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return bool(
            getattr(user, "is_superuser", False)
            or is_admin_role(user)
            or is_supervisor_role(user)
        )


class StaffUserOnly(BasePermission):
    """Allow staff/customer users. Block platform super admins."""

    message = "Staff user only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and not getattr(user, "is_superuser", False)
        )
