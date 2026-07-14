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
        # Roles may live on the generic staff role or the government-staff role
        # (e.g. "govt_panchayat_driver"). Match either as long as it names a
        # field-collection role.
        role_names = []
        for attr in (
            "staffusertype_id",
            "governmentusertype_id",
            "contractorusertype_id",
        ):
            role_obj = getattr(user, attr, None)
            name = (getattr(role_obj, "name", "") or "").lower()
            if name:
                role_names.append(name)
        field_role_markers = ("driver", "operator", "field")
        return any(
            any(marker in role_name for marker in field_role_markers)
            for role_name in role_names
        )
