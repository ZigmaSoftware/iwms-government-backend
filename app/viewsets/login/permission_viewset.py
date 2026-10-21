from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.leader_management.district_leader_login import DistrictLeaderLogin
from app.models.masters.leader_management.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.leader_management.state_leader_login import StateLeaderLogin
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.login.login_serializer import LoginSerializer


class PermissionViewSet(ViewSet):
    """
    The signed-in user's permissions — the single source for both the web
    app and the mobile app (login no longer returns them).

    Built by the same LoginSerializer payload builders login uses, so the
    result is exactly what ModulePermissionMiddleware enforces: local-body
    intersection, Staff Access Configuration and app modules included.
    """
    throttle_scope = "permission"

    def list(self, request):
        """
        GET /api/v1/login/my-permissions/
        Returns latest permissions for current user.
        """
        payload = self._resolve_permission_payload_for_user(request.user)

        return Response(
            {
                "permissions": payload.get("permissions", {}),
                "permission_details": payload.get("permission_details", {}),
                "column_permissions": payload.get("column_permissions", {}),
                "module_access": payload.get("module_access", []),
                "app_surfaces": payload.get("app_surfaces", []),
                "app_modules": payload.get("app_modules", []),
                "app_screens": payload.get("app_screens", {}),
                "landing": payload.get("landing"),
                "permission_version": payload.get("permission_version"),
                "generated_at": payload.get("generated_at"),
                "timestamp": timezone.now().isoformat(),
                "source": "database"
            },
            status=status.HTTP_200_OK
        )

    def _resolve_permission_payload_for_user(self, user):
        """Mirror of LoginSerializer's provider routing for an already
        authenticated user (see JWTUserAuthentication for the user kinds)."""
        builder = LoginSerializer()

        if isinstance(user, Staffcreation):
            # Login sends staff super admins through the platform path.
            if user.is_superuser:
                return builder._build_platform_payload(user)
            return builder._build_staff_payload(user)

        if isinstance(user, CustomerCreation):
            return builder._build_customer_payload(user)

        if isinstance(user, PanchayatLeaderLogin):
            return builder._build_panchayat_leader_payload(user)
        if isinstance(user, DistrictLeaderLogin):
            return builder._build_district_leader_payload(user)
        if isinstance(user, StateLeaderLogin):
            return builder._build_state_leader_payload(user)

        # Platform User account, possibly linked to a staff or customer row.
        staff = getattr(user, "staff", None)
        if staff:
            if staff.is_superuser:
                return builder._build_platform_payload(user)
            return builder._build_staff_payload(staff, login_user=user)

        customer = getattr(user, "customer", None)
        if customer:
            return builder._build_customer_payload(customer, login_user=user)

        if getattr(user, "is_superuser", False):
            return builder._build_platform_payload(user)

        return {}
