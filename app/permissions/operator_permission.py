from rest_framework.permissions import BasePermission


class IsOperatorRole(BasePermission):
    """Only allow Staffcreation users whose staffusertype is Company Operator."""

    message = "Operator role required"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        role_obj = getattr(user, "staffusertype_id", None)
        role_name = (getattr(role_obj, "name", "") or "").lower()
        return role_name in (
            "company_operator",
            "company operator",
            "operator",
        )
