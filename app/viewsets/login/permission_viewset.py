from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from app.models.customers.customercreation import CustomerCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.models.screen_managements.companyuserscreenpermission import UserScreenPermission
from app.utils.permission_response import resolve_permission_payload

CompanyUserScreenPermission = UserScreenPermission


class PermissionViewSet(ViewSet):
    """
    Fetch current user's permissions dynamically from DB.
    Works with custom Staffcreation model (no dependency on Django User).
    """

    def list(self, request):
        """
        GET /api/v1/my-permissions/
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
                "landing": payload.get("landing"),
                "permission_version": payload.get("permission_version"),
                "generated_at": payload.get("generated_at"),
                "timestamp": timezone.now().isoformat(),
                "source": "database"
            },
            status=status.HTTP_200_OK
        )

    # ------------------------------------------------------------------
    # CORE LOGIC
    # ------------------------------------------------------------------

    def _resolve_permission_payload_for_user(self, user):
        if getattr(user, "is_superuser", False):
            return resolve_permission_payload(
                include_all=True,
                role_name="superadmin",
                user_type="platform",
            )

        staff_user = self._resolve_staff_user(user)
        if staff_user:
            user_type = getattr(staff_user, "user_type_id", None)
            staff_usertype = getattr(staff_user, "staffusertype_id", None)
            contractor_usertype = getattr(staff_user, "contractorusertype_id", None)
            government_usertype = getattr(staff_user, "governmentusertype_id", None)

            if not user_type:
                return {}

            role_name = (
                getattr(staff_usertype, "name", None)
                or getattr(contractor_usertype, "name", None)
                or getattr(government_usertype, "name", None)
                or getattr(user_type, "name", None)
            )
            return resolve_permission_payload(
                usertype_unique_id=user_type.unique_id,
                staffusertype_unique_id=staff_usertype.unique_id if staff_usertype else None,
                contractorusertype_unique_id=contractor_usertype.unique_id if contractor_usertype else None,
                governmentusertype_unique_id=government_usertype.unique_id if government_usertype else None,
                role_name=role_name,
                user_type=getattr(user_type, "name", None),
            )

        customer_user = self._resolve_customer_user(user)
        if customer_user:
            user_type = getattr(customer_user, "user_type_id", None)
            if not user_type:
                return {}

            return resolve_permission_payload(
                usertype_unique_id=user_type.unique_id,
                role_name="customer",
                user_type=getattr(user_type, "name", None),
            )

        return {}

    def _resolve_permissions_for_user(self, user):
        """
        Extract user's role and resolve permissions.
        """

        # ✅ SUPERADMIN → FULL ACCESS
        if getattr(user, "is_superuser", False):
            return self._get_all_permissions()

        # ✅ Resolve staff user
        staff_user = self._resolve_staff_user(user)
        if not staff_user:
            return {}

        # ✅ Get user type and roles
        user_type = getattr(staff_user, "user_type_id", None)
        staff_usertype = getattr(staff_user, "staffusertype_id", None)
        contractor_usertype = getattr(staff_user, "contractorusertype_id", None)
        government_usertype = getattr(staff_user, "governmentusertype_id", None)

        if not user_type:
            return {}

        # ✅ Return filtered permissions
        return self._format_permissions(
            usertype_unique_id=user_type.unique_id,
            staffusertype_unique_id=staff_usertype.unique_id if staff_usertype else None,
            contractorusertype_unique_id=contractor_usertype.unique_id if contractor_usertype else None,
            governmentusertype_unique_id=government_usertype.unique_id if government_usertype else None,
        )

    def _resolve_permission_details_for_user(self, user):
        if getattr(user, "is_superuser", False):
            return resolve_permission_payload(include_all=True)["permission_details"]

        staff_user = self._resolve_staff_user(user)
        if not staff_user:
            return {}

        user_type = getattr(staff_user, "user_type_id", None)
        staff_usertype = getattr(staff_user, "staffusertype_id", None)
        contractor_usertype = getattr(staff_user, "contractorusertype_id", None)
        government_usertype = getattr(staff_user, "governmentusertype_id", None)

        if not user_type:
            return {}

        return resolve_permission_payload(
            usertype_unique_id=user_type.unique_id,
            staffusertype_unique_id=staff_usertype.unique_id if staff_usertype else None,
            contractorusertype_unique_id=contractor_usertype.unique_id if contractor_usertype else None,
            governmentusertype_unique_id=government_usertype.unique_id if government_usertype else None,
        )["permission_details"]

    def _resolve_column_permissions_for_user(self, user):
        if getattr(user, "is_superuser", False):
            return resolve_permission_payload(include_all=True)["column_permissions"]

        staff_user = self._resolve_staff_user(user)
        if not staff_user:
            return {}

        user_type = getattr(staff_user, "user_type_id", None)
        staff_usertype = getattr(staff_user, "staffusertype_id", None)
        contractor_usertype = getattr(staff_user, "contractorusertype_id", None)
        government_usertype = getattr(staff_user, "governmentusertype_id", None)

        if not user_type:
            return {}

        return resolve_permission_payload(
            usertype_unique_id=user_type.unique_id,
            staffusertype_unique_id=staff_usertype.unique_id if staff_usertype else None,
            contractorusertype_unique_id=contractor_usertype.unique_id if contractor_usertype else None,
            governmentusertype_unique_id=government_usertype.unique_id if government_usertype else None,
        )["column_permissions"]

    # ------------------------------------------------------------------
    # SUPERADMIN FULL PERMISSION
    # ------------------------------------------------------------------

    def _get_all_permissions(self):
        """
        Return ALL permissions for superadmin
        """

        queryset = UserScreenPermission.objects.filter(
            is_active=True,
            is_deleted=False
        ).select_related(
            "mainscreen_id",
            "userscreen_id",
            "userscreenaction_id",
        )

        permissions = {}

        for perm in queryset.order_by("order_no"):
            main_name = perm.mainscreen_id.mainscreen_name
            screen_name = perm.userscreen_id.userscreen_name
            action_name = perm.userscreenaction_id.action_name

            module_map = permissions.setdefault(main_name, {})
            action_list = module_map.setdefault(screen_name, [])

            if action_name not in action_list:
                action_list.append(action_name)

        return permissions

    # ------------------------------------------------------------------
    # STAFF RESOLVER
    # ------------------------------------------------------------------

    def _resolve_staff_user(self, user):
        """
        Extract Staffcreation object from various user representations.
        """

        # Case 1: user itself is Staffcreation
        if isinstance(user, Staffcreation):
            return user

        # Case 2: user has staff relation
        staff = getattr(user, "staff", None)
        if staff:
            return staff
        staff = getattr(user, "staff_id", None)
        if staff:
            return staff

        # Case 3: try lookup using unique_id (from JWT)
        user_unique_id = None

        if hasattr(user, "unique_id"):
            user_unique_id = user.unique_id
        elif hasattr(user, "staff_unique_id"):
            user_unique_id = user.staff_unique_id

        if user_unique_id:
            try:
                return Staffcreation.objects.filter(
                    staff_unique_id=user_unique_id
                ).first()
            except Exception:
                return None

        return None

    def _resolve_customer_user(self, user):
        if isinstance(user, CustomerCreation):
            return user

        customer = getattr(user, "customer", None)
        if customer:
            return customer
        customer = getattr(user, "customer_id", None)
        if customer:
            return customer

        user_unique_id = getattr(user, "unique_id", None)
        if user_unique_id:
            return CustomerCreation.objects.filter(unique_id=user_unique_id).first()

        return None

    # ------------------------------------------------------------------
    # PERMISSION FORMATTER
    # ------------------------------------------------------------------

    def _format_permissions(
        self,
        usertype_unique_id=None,
        staffusertype_unique_id=None,
        contractorusertype_unique_id=None,
        governmentusertype_unique_id=None,
    ):
        """
        Build permission structure:
        {
            "Module": {
                "Screen": ["view", "add", "edit"]
            }
        }
        """

        if not usertype_unique_id:
            return {}

        queryset = UserScreenPermission.objects.filter(
            is_active=True,
            is_deleted=False,
            usertype_id_id=usertype_unique_id,
        ).select_related(
            "mainscreen_id",
            "userscreen_id",
            "userscreenaction_id",
        )

        # Handle staffusertype condition
        if staffusertype_unique_id:
            queryset = queryset.filter(
                staffusertype_id_id=staffusertype_unique_id
            )
        elif contractorusertype_unique_id:
            queryset = queryset.filter(
                contractorusertype_id_id=contractorusertype_unique_id
            )
        elif governmentusertype_unique_id:
            queryset = queryset.filter(
                governmentusertype_id_id=governmentusertype_unique_id
            )
        else:
            queryset = queryset.filter(
                staffusertype_id__isnull=True,
                contractorusertype_id__isnull=True,
                governmentusertype_id__isnull=True,
            )

        permissions = {}

        for perm in queryset.order_by("order_no"):
            main_name = perm.mainscreen_id.mainscreen_name
            screen_name = perm.userscreen_id.userscreen_name
            action_name = perm.userscreenaction_id.action_name

            module_map = permissions.setdefault(main_name, {})
            action_list = module_map.setdefault(screen_name, [])

            if action_name not in action_list:
                action_list.append(action_name)

        return permissions
    
