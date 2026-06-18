from rest_framework.permissions import BasePermission, SAFE_METHODS


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
    """Allow staff users with an admin role."""

    message = "Company admin only"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        role = getattr(getattr(user, "staffusertype_id", None), "name", "")
        return bool(
            user
            and user.is_authenticated
            and not getattr(user, "is_superuser", False)
            and (role or "").lower() in ["admin","company_admin","company admin"]
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

        role = getattr(getattr(user, "staffusertype_id", None), "name", "")
        is_company_admin = bool(
            not getattr(user, "is_superuser", False)
            and (role or "").lower() in ["admin","company_admin","company admin"]
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

        # ✅ Company Admin
        role = getattr(getattr(user, "staffusertype_id", None), "name", "")
        is_company_admin = bool(
            not getattr(user, "is_superuser", False)
            and (role or "").lower() in ["admin","company_admin","company admin"]
        )

        if is_company_admin:
            # 🔒 Allow only SAFE methods (GET, HEAD, OPTIONS)
            return request.method in SAFE_METHODS

        return False


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
