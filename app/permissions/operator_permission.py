from rest_framework.permissions import BasePermission


class IsOperatorRole(BasePermission):
    """Allow Staffcreation users whose staffusertype is a field-collection role.

    The driver and operator mobile apps were merged, so the shared
    operator-mobile endpoints (my-trip-today / validate-bin-qr / scan-bin /
    trip-history) must accept both driver and operator roles.
    """

    message = "Driver or operator role required"

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        from app.utils.roles import effective_role_name

        role_name = effective_role_name(user)
        return any(marker in role_name for marker in ("driver", "operator", "field"))
