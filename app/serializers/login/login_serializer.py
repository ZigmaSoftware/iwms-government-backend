from rest_framework import serializers
from django.contrib.auth.hashers import check_password, identify_hasher
from django.db.models import F, Q
from django.utils import timezone

from app.models.user_creations.staffcreation import Staffcreation
from app.models.customers.customercreation import CustomerCreation
from app.models.role_assigns.userType import UserType
from app.models.superadmin_masters.auth_user import User
from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin
from app.models.masters.district_leader_login import DistrictLeaderLogin

from app.utils.permission_response import finalize_permission_payload, resolve_permission_payload
from app.utils.password_encryption import decrypt_password

PASSWORD_EXPIRY_DAYS = 90


def _is_password_expired(password_crt_date):
    """Return True if the password is older than PASSWORD_EXPIRY_DAYS days."""
    if not password_crt_date:
        return False
    age = timezone.now() - password_crt_date
    return age.days >= PASSWORD_EXPIRY_DAYS


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    login_type = serializers.ChoiceField(
        choices=["auto", "staff", "customer", "platform", "contractor", "panchayat_leader", "district_leader"],
        default="auto",
        required=False
    )

    @staticmethod
    def _password_matches(raw_password, stored_password):
        if stored_password is None:
            return False
        try:
            identify_hasher(stored_password)
        except ValueError:
            decrypted_password = decrypt_password(stored_password)
            if decrypted_password:
                return raw_password == decrypted_password
            return raw_password == stored_password
        return check_password(raw_password, stored_password)

    def _determine_order(self, login_type):
        if login_type == "staff":
            return ["staff", "customer", "platform"]
        if login_type == "customer":
            return ["customer", "staff", "platform"]
        if login_type == "platform":
            return ["platform"]
        if login_type == "contractor":
            return ["contractor", "staff", "customer", "platform"]
        if login_type == "panchayat_leader":
            return ["panchayat_leader"]
        if login_type == "district_leader":
            return ["district_leader"]
        return ["customer", "staff", "platform", "contractor"]

    def _format_permissions(self, queryset):
        permissions = {}
        for perm in queryset.order_by("order_no"):
            main_name = perm.mainscreen_id.mainscreen_name
            screen_name = perm.userscreen_id.userscreen_name
            action_name = perm.userscreenaction_id.action_name

            screen_map = permissions.setdefault(main_name, {})
            actions = screen_map.setdefault(screen_name, [])
            if action_name not in actions:
                actions.append(action_name)

        return permissions

    def _resolve_permission_payload(
        self,
        *,
        usertype_unique_id=None,
        staffusertype_unique_id=None,
        contractorusertype_unique_id=None,
        governmentusertype_unique_id=None,
        include_all=False,
        role_name=None,
        user_type=None,
    ):
        return resolve_permission_payload(
            usertype_unique_id=usertype_unique_id,
            staffusertype_unique_id=staffusertype_unique_id,
            contractorusertype_unique_id=contractorusertype_unique_id,
            governmentusertype_unique_id=governmentusertype_unique_id,
            include_all=include_all,
            role_name=role_name,
            user_type=user_type,
        )

    def _resolve_permissions(
        self,
        *,
        usertype_unique_id=None,
        staffusertype_unique_id=None,
        contractorusertype_unique_id=None,
        include_all=False
    ):
        payload = self._resolve_permission_payload(
            usertype_unique_id=usertype_unique_id,
            staffusertype_unique_id=staffusertype_unique_id,
            contractorusertype_unique_id=contractorusertype_unique_id,
            include_all=include_all,
        )
        return payload["permissions"]

    def _apply_role_defaults(self, permissions, role_name):
        if not role_name:
            return permissions

        defaults = {
            "driver": {
                "customers": {
                    "customercreations": ["view"],
                },
                "process": {
                    
                },
                "user-creations": {
                    "alternative-stafftemplate": ["view"],
                },
            },
            "operator": {
                "customers": {
                    "customercreations": ["view"],
                },
                "process": {
                    
                },
                "user-creations": {
                    "alternative-stafftemplate": ["view"],
                },
            },
        }

        role_defaults = defaults.get(role_name.lower())
        if not role_defaults:
            return permissions

        for module_name, screens in role_defaults.items():
            module_perms = permissions.setdefault(module_name, {})
            for screen_name, actions in screens.items():
                existing = set(module_perms.get(screen_name, []))
                merged = existing.union(actions)
                module_perms[screen_name] = list(merged)

        return permissions

    def _build_staff_payload(self, staff_record, login_user=None):
        login_user = login_user or staff_record

        if not staff_record.login_enabled:
            Staffcreation.objects.filter(pk=staff_record.pk).update(
                failed_login_attempts=F("failed_login_attempts") + 1
            )
            raise serializers.ValidationError("Login is disabled for this user")

        if staff_record.approval_status != Staffcreation.APPROVAL_APPROVED:
            Staffcreation.objects.filter(pk=staff_record.pk).update(
                failed_login_attempts=F("failed_login_attempts") + 1
            )
            raise serializers.ValidationError(
                f"User approval status is {staff_record.approval_status}"
            )

        user_type = staff_record.user_type_id or getattr(login_user, "user_type_id", None)
        if not user_type:
            raise serializers.ValidationError("Invalid user type")

        allowed_roles = ["staff", "contractor", "government"]

        if user_type.name.lower() not in allowed_roles:
            raise serializers.ValidationError("Unsupported user role type")

        staff_usertype = getattr(staff_record, "staffusertype_id", None) or getattr(login_user, "staffusertype_id", None)
        contractor_usertype = getattr(staff_record, "contractorusertype_id", None) or getattr(login_user, "contractorusertype_id", None)
        government_usertype = getattr(staff_record, "governmentusertype_id", None) or getattr(login_user, "governmentusertype_id", None)
        role_usertype = staff_usertype or contractor_usertype or government_usertype

        if not role_usertype:
            raise serializers.ValidationError("Staff role not assigned")

        permission_payload = self._resolve_permission_payload(
            usertype_unique_id=user_type.unique_id,
            staffusertype_unique_id=staff_usertype.unique_id if staff_usertype else None,
            contractorusertype_unique_id=contractor_usertype.unique_id if contractor_usertype else None,
            governmentusertype_unique_id=government_usertype.unique_id if government_usertype else None,
            role_name=role_usertype.name,
            user_type="government" if government_usertype else "contractor" if contractor_usertype else "staff",
        )
        permissions = permission_payload["permissions"]

        if not permissions:
            permissions = self._apply_role_defaults(permissions, role_usertype.name)
            permission_payload = finalize_permission_payload(
                permission_payload,
                permissions=permissions,
                role_name=role_usertype.name,
                user_type="government" if government_usertype else "contractor" if contractor_usertype else "staff",
            )

        password_expired = _is_password_expired(getattr(staff_record, "password_crt_date", None))

        return {
            "user": login_user,
            "permissions": permissions,
            "permission_details": permission_payload["permission_details"],
            "column_permissions": permission_payload["column_permissions"],
            "module_access": permission_payload["module_access"],
            "app_surfaces": permission_payload["app_surfaces"],
            "landing": permission_payload["landing"],
            "permission_version": permission_payload["permission_version"],
            "generated_at": permission_payload["generated_at"],
            "user_type": "government" if government_usertype else "contractor" if contractor_usertype else "staff",
            "staffusertype_id": staff_usertype.unique_id if staff_usertype else None,
            "contractorusertype_id": contractor_usertype.unique_id if contractor_usertype else None,
            "governmentusertype_id": government_usertype.unique_id if government_usertype else None,
            "profile_object": staff_record,
            "password_expired": password_expired,
        }

    def _build_customer_payload(self, customer_record, login_user=None):
        login_user = login_user or customer_record

        user_type = getattr(login_user, "user_type_id", None)
        if not user_type:
            user_type = UserType.objects.filter(name__iexact="customer").first()
        if not user_type:
            raise serializers.ValidationError("Customer user type is not configured")

        permission_payload = self._resolve_permission_payload(
            usertype_unique_id=user_type.unique_id,
            staffusertype_unique_id=None,
            role_name="customer",
            user_type="customer",
        )
        permissions = permission_payload["permissions"]

        password_expired = _is_password_expired(getattr(customer_record, "password_crt_date", None))

        return {
            "user": login_user,
            "permissions": permissions,
            "permission_details": permission_payload["permission_details"],
            "column_permissions": permission_payload["column_permissions"],
            "module_access": permission_payload["module_access"],
            "app_surfaces": permission_payload["app_surfaces"],
            "landing": permission_payload["landing"],
            "permission_version": permission_payload["permission_version"],
            "generated_at": permission_payload["generated_at"],
            "user_type": "customer",
            "staffusertype_id": None,
            "profile_object": customer_record,
            "password_expired": password_expired,
        }

    def _build_platform_payload(self, user):
        permission_payload = self._resolve_permission_payload(
            include_all=True,
            role_name="superadmin",
            user_type="platform",
        )
        permissions = permission_payload["permissions"]

        permissions = self._apply_role_defaults(permissions, "superadmin")
        permission_payload = finalize_permission_payload(
            permission_payload,
            permissions=permissions,
            role_name="superadmin",
            user_type="platform",
        )

        return {
            "user": user,
            "permissions": permissions,
            "permission_details": permission_payload["permission_details"],
            "column_permissions": permission_payload["column_permissions"],
            "module_access": permission_payload["module_access"],
            "app_surfaces": permission_payload["app_surfaces"],
            "landing": permission_payload["landing"],
            "permission_version": permission_payload["permission_version"],
            "generated_at": permission_payload["generated_at"],
            "user_type": "platform",
            "staffusertype_id": getattr(getattr(user, "staffusertype_id", None), "unique_id", None),
        }

    def _authenticate_customer(self, username, password):
        candidates = (
            CustomerCreation.objects
            .filter(is_active=True, is_deleted=False)
            .filter(
                Q(username__iexact=username) |
                Q(customer_name__iexact=username) |
                Q(contact_no__iexact=username)
            )
        )

        for candidate in candidates:
            if not self._password_matches(password, candidate.password):
                continue

            return self._build_customer_payload(candidate)

        return None

    def _authenticate_staff(self, username, password):
        lookup_filters = (
            Q(employee_name__iexact=username) |
            Q(username__iexact=username) |
            Q(emp_id__iexact=username)
        )

        queryset = (
            Staffcreation.objects
            .select_related("user_type_id", "staffusertype_id", "contractorusertype_id", "governmentusertype_id", "personal_details")
            .filter(is_active=True, is_deleted=False)
            .filter(lookup_filters)
        )

        for candidate in queryset:
            if not self._password_matches(password, candidate.password):
                Staffcreation.objects.filter(pk=candidate.pk).update(
                    failed_login_attempts=F("failed_login_attempts") + 1
                )
                continue

            if candidate.is_superuser:
                # Platform super admins live in a different table/path.
                return None

            if not candidate.login_enabled:
                Staffcreation.objects.filter(pk=candidate.pk).update(
                    failed_login_attempts=F("failed_login_attempts") + 1
                )
                raise serializers.ValidationError("Login is disabled for this user")

            if candidate.approval_status != Staffcreation.APPROVAL_APPROVED:
                Staffcreation.objects.filter(pk=candidate.pk).update(
                    failed_login_attempts=F("failed_login_attempts") + 1
                )
                raise serializers.ValidationError(
                    f"User approval status is {candidate.approval_status}"
                )

            return self._build_staff_payload(candidate)

        return None

    def _authenticate_platform(self, username, password):
        user = (
            User.objects
            .select_related(
                "staff_id__user_type_id",
                "staff_id__staffusertype_id",
                "staff_id__contractorusertype_id",
                "staff_id__governmentusertype_id",
                "user_type_id",
                "staffusertype_id",
            )
            .filter(username__iexact=username, is_active=True, is_deleted=False)
            .first()
        )

        if not user or not self._password_matches(password, user.password):
            return None

        staff_record = getattr(user, "staff_id", None)
        if staff_record:
            if staff_record.is_superuser:
                return self._build_platform_payload(user)
            return self._build_staff_payload(staff_record, login_user=user)

        customer_record = getattr(user, "customer_id", None)
        if customer_record:
            return self._build_customer_payload(customer_record, login_user=user)

        if user.is_superuser:
            return self._build_platform_payload(user)

        return None

    def _build_panchayat_leader_payload(self, leader):
        panchayat = leader.panchayat_id

        return {
            "user": leader,
            "permissions": {},
            "permission_details": {},
            "column_permissions": {},
            "module_access": [],
            "app_surfaces": [],
            "landing": None,
            "permission_version": None,
            "generated_at": None,
            "user_type": "panchayat_leader",
            "staffusertype_id": None,
            "contractorusertype_id": None,
            "profile_object": leader,
        }

    def _authenticate_panchayat_leader(self, username, password):
        leader = (
            PanchayatLeaderLogin.objects
            .select_related("panchayat_id")
            .filter(is_active=True, is_deleted=False)
            .filter(Q(username__iexact=username) | Q(email__iexact=username))
            .first()
        )

        if not leader:
            return None

        if not self._password_matches(password, leader.password):
            return None

        return self._build_panchayat_leader_payload(leader)

    def _build_district_leader_payload(self, leader):
        district = leader.district_id

        return {
            "user": leader,
            "permissions": {},
            "permission_details": {},
            "column_permissions": {},
            "module_access": [],
            "app_surfaces": [],
            "landing": None,
            "permission_version": None,
            "generated_at": None,
            "user_type": "district_leader",
            "staffusertype_id": None,
            "contractorusertype_id": None,
            "profile_object": leader,
        }

    def _authenticate_district_leader(self, username, password):
        leader = (
            DistrictLeaderLogin.objects
            .select_related("district_id")
            .filter(is_active=True, is_deleted=False)
            .filter(Q(username__iexact=username) | Q(email__iexact=username))
            .first()
        )

        if not leader:
            return None

        if not self._password_matches(password, leader.password):
            return None

        return self._build_district_leader_payload(leader)

    def validate(self, attrs):
        username = attrs["username"].strip()
        password = attrs["password"].strip()
        login_type = attrs.get("login_type", "auto")

        first_error = None
        for provider in self._determine_order(login_type):
            authenticate_method = getattr(self, f"_authenticate_{provider}", None)
            if not authenticate_method:
                continue
            try:
                data = authenticate_method(username, password)
            except serializers.ValidationError as exc:
                if first_error is None:
                    first_error = exc
                continue
            if data:
                attrs.update(data)
                return attrs

        if first_error:
            raise first_error

        raise serializers.ValidationError("Invalid username or password")
