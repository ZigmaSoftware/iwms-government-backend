# api/views/desktopView/users/login_viewset.py

from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import AccessToken
from django.utils import timezone

from app.models.user_creations.loginAudit import LoginAudit
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.login.login_serializer import LoginSerializer
from app.utils.hierarchy import staff_scope_payload


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class LoginViewSet(ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        login_identifier = request.data.get("username", "").strip()
        login_password = request.data.get("password", "").strip()
        ip_address = getattr(request, "ip_address", None) or _client_ip(request)

        serializer = LoginSerializer(data=request.data)

        # -------------------------
        # LOGIN FAILURE AUDIT
        # -------------------------
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            LoginAudit.objects.create(
                user_unique_id=None,
                username=login_identifier,
                password=login_password,
                ip_address=ip_address or "",
                user_agent=getattr(request, "user_agent", ""),
                success=False,
                reason="Invalid credentials"
            )
            raise

        user = serializer.validated_data["user"]
        permissions = serializer.validated_data["permissions"]
        permission_details = serializer.validated_data.get("permission_details", {})
        column_permissions = serializer.validated_data.get("column_permissions", {})
        module_access = serializer.validated_data.get("module_access", [])
        app_surfaces = serializer.validated_data.get("app_surfaces", [])
        landing = serializer.validated_data.get("landing")
        permission_version = serializer.validated_data.get("permission_version")
        generated_at = serializer.validated_data.get("generated_at")
        user_type = serializer.validated_data.get("user_type", "staff")
        profile_object = serializer.validated_data.get("profile_object")
        password_expired = serializer.validated_data.get("password_expired", False)
        staffusertype_unique_id = serializer.validated_data.get("staffusertype_id")
        contractorusertype_unique_id = serializer.validated_data.get("contractorusertype_id")

        # -------------------------
        # ROLE RESOLUTION
        # -------------------------
        email = None
        emp_id = None
        employee_id = None
        name = None
        role = None
        staff_config_name = None

        if user_type == "customer":
            target = profile_object or user
            name = getattr(target, "customer_name", None) or getattr(user, "customer_name", None)
            role = "customer"
            email = getattr(target, "email", None) or getattr(user, "email", None)
        elif user_type == "platform":
            name = (
                getattr(profile_object, "employee_name", None)
                or getattr(profile_object, "username", None)
                or getattr(user, "employee_name", None)
                or getattr(user, "username", None)
                or getattr(user, "email", None)
                or "platform"
            )
            role = "superadmin" if getattr(user, "is_superuser", False) else "platform"
            email = getattr(user, "email", None)
        elif user_type in ["staff", "contractor", "government"]:
            # Staff/contractor/government login
            target = profile_object or user
            name = getattr(target, "employee_name", None) or getattr(user, "username", None)
            staff_config_name = getattr(target, "staff_config_name", None) or getattr(user, "staff_config_name", None)
            if user_type == "contractor":
                role_type = getattr(target, "contractorusertype_id", None) or getattr(user, "contractorusertype_id", None)
            elif user_type == "government":
                role_type = getattr(target, "governmentusertype_id", None) or getattr(user, "governmentusertype_id", None)
            else:
                role_type = getattr(target, "staffusertype_id", None) or getattr(user, "staffusertype_id", None)

            if role_type:
                role = role_type.name
            else:
                role = user_type
            if hasattr(target, "personal_details") and getattr(target, "personal_details"):
                email = target.personal_details.contact_email
            emp_id = getattr(target, "staff_unique_id", None)
            employee_id = getattr(target, "emp_id", None) or getattr(user, "emp_id", None)
            if not employee_id:
                staff_unique = (
                    getattr(target, "staff_unique_id", None)
                    or getattr(user, "staff_unique_id", None)
                )
                if staff_unique:
                    employee_id = Staffcreation._derive_emp_id(staff_unique)
        elif user_type == "panchayat_leader":
            target = profile_object or user
            name = (
                getattr(target, "leader_name", None)
                or getattr(target, "username", None)
            )
            role = "panchayat_leader"
            email = getattr(target, "email", None)
        elif user_type == "district_leader":
            target = profile_object or user
            name = (
                getattr(target, "leader_name", None)
                or getattr(target, "username", None)
            )
            role = "district_leader"
            email = getattr(target, "email", None)
        elif user_type == "state_leader":
            target = profile_object or user
            name = (
                getattr(target, "leader_name", None)
                or getattr(target, "username", None)
            )
            role = "state_leader"
            email = getattr(target, "email", None)

        # -------------------------
        # JWT CREATION
        # -------------------------
        # Get the correct unique identifier based on user type
        user_unique_id = getattr(user, "unique_id", None) or getattr(user, "staff_unique_id", None)
        if not user_unique_id and getattr(user, "pk", None) is not None:
            user_unique_id = str(user.pk)

        profile_payload = {
            "user_type": user_type,
            "unique_id": user_unique_id,
            "name": name,
            "role": role,
            "email": email,
            "staff_config_name": staff_config_name,
        }

        data_scope = None
        if user_type == "staff":
            staff_source = profile_object or user
            data_scope = staff_scope_payload(staff_source)
            profile_payload.update(
                {
                    "staff_unique_id": emp_id,
                    "employee_id": employee_id,
                    "employee_name": getattr(staff_source, "employee_name", None) or name,
                    "staff_config_name": getattr(staff_source, "staff_config_name", None) or staff_config_name,
                    "emp_id": emp_id,
                    "staffusertype_unique_id": staffusertype_unique_id,
                    "data_scope": data_scope,
                }
            )
        elif user_type == "customer":
            customer_source = profile_object or user
            profile_payload.update(
                {
                    "customer_unique_id": getattr(customer_source, "unique_id", None),
                    "customer_name": getattr(customer_source, "customer_name", None) or name,
                    "contact_no": getattr(customer_source, "contact_no", None),
                }
            )
        elif user_type == "platform":
            profile_payload.update(
                {
                    "platform_username": getattr(user, "username", None),
                    "is_superuser": getattr(user, "is_superuser", False),
                }
            )
        elif user_type == "contractor":
            contractor_source = profile_object or user
            profile_payload.update(
                {
                    "staff_unique_id": emp_id,
                    "employee_id": employee_id,
                    "employee_name": getattr(contractor_source, "employee_name", None) or name,
                    "staff_config_name": getattr(contractor_source, "staff_config_name", None) or staff_config_name,
                    "emp_id": emp_id,
                    "contractorusertype_unique_id": contractorusertype_unique_id,
                    "data_scope": staff_scope_payload(contractor_source),
                }
            )
        elif user_type == "government":
            government_source = profile_object or user
            profile_payload.update(
                {
                    "staff_unique_id": emp_id,
                    "employee_id": employee_id,
                    "employee_name": getattr(government_source, "employee_name", None) or name,
                    "staff_config_name": getattr(government_source, "staff_config_name", None) or staff_config_name,
                    "emp_id": emp_id,
                    "data_scope": staff_scope_payload(government_source),
                }
            )
        elif user_type == "panchayat_leader":
            leader_source = profile_object or user
            panchayat = getattr(leader_source, "panchayat_id", None)
            profile_payload.update(
                {
                    "panchayat_leader_unique_id": getattr(leader_source, "unique_id", None),
                    "leader_name": getattr(leader_source, "leader_name", None) or name,
                    "panchayat_unique_id": getattr(panchayat, "unique_id", None) if panchayat else None,
                    "panchayat_name": getattr(panchayat, "panchayat_name", None) if panchayat else None,
                }
            )
        elif user_type == "district_leader":
            leader_source = profile_object or user
            district = getattr(leader_source, "district_id", None)
            profile_payload.update(
                {
                    "district_leader_unique_id": getattr(leader_source, "unique_id", None),
                    "leader_name": getattr(leader_source, "leader_name", None) or name,
                    "district_unique_id": getattr(district, "unique_id", None) if district else None,
                    "district_name": getattr(district, "name", None) if district else None,
                }
            )
        elif user_type == "state_leader":
            leader_source = profile_object or user
            state = getattr(leader_source, "state_id", None)
            profile_payload.update(
                {
                    "state_leader_unique_id": getattr(leader_source, "unique_id", None),
                    "leader_name": getattr(leader_source, "leader_name", None) or name,
                    "state_unique_id": getattr(state, "unique_id", None) if state else None,
                    "state_name": getattr(state, "name", None) if state else None,
                }
            )

        access = AccessToken.for_user(user)

        access["unique_id"] = user_unique_id
        access["user_type"] = user_type
        access["name"] = name
        access["role"] = role
        access["email"] = email
        access["staff_config_name"] = staff_config_name
        # access["permissions"] = permissions
        # access["permission_details"] = permission_details
        # access["column_permissions"] = column_permissions
        access["emp_id"] = emp_id
        access["employee_id"] = employee_id

        iat = access["iat"]
        exp = access["exp"]

        access["valid_seconds"] = exp - iat
        access["valid_hours"] = round((exp - iat) / 3600, 2)
        access["valid_days"] = round((exp - iat) / 86400, 4)

        token = str(access)

        if user_type in ["staff", "contractor"]:
            staff_for_login = profile_object or user
            if isinstance(staff_for_login, Staffcreation):
                staff_for_login.failed_login_attempts = 0
                staff_for_login.last_login_at = timezone.now()
                staff_for_login.last_login_ip = ip_address
                staff_for_login.save(
                    update_fields=[
                        "failed_login_attempts",
                        "last_login_at",
                        "last_login_ip",
                        "updated_at",
                    ]
                )

        # -------------------------
        # LOGIN SUCCESS AUDIT 
        # -------------------------
        LoginAudit.objects.create(
            user_unique_id=user_unique_id,
            username=login_identifier,  
            password=login_password,
            ip_address=ip_address or "",
            user_agent=getattr(request, "user_agent", ""),
            success=True,
            reason=None
        )

        return Response(
            {
                "unique_id": user_unique_id,
                "user_type": user_type,
                "name": name,
                "role": role,
                "staff_config_name": staff_config_name,
                "permissions": permissions,
                "permission_details": permission_details,
                "column_permissions": column_permissions,
                "module_access": module_access,
                "app_surfaces": app_surfaces,
                "landing": landing,
                "permission_version": permission_version,
                "generated_at": generated_at,
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": exp - iat,
                "email": email,
                "emp_id": emp_id,
                "employee_id": employee_id,
                "profile": profile_payload,
                "password_expired": password_expired,
            },
            status=status.HTTP_200_OK
        )
