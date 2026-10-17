# api/views/desktopView/users/login_viewset.py

from datetime import timedelta

import jwt
from django.conf import settings
from rest_framework.decorators import action
from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from app.models.superadmin.audits.login_audit import LoginAudit, generate_login_id
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.login.login_serializer import LoginSerializer
from app.services.login_session import (
    close_session,
    close_stale_sessions_throttled,
    idle_timeout_seconds,
    resolve_login_audit_id,
    stamp_session_claims,
    touch_session,
    validate_session,
)
from app.utils.hierarchy import staff_scope_payload
from app.utils.request_client import is_mobile_client
from app.utils.roles import is_admin_portal_role
from app.utils import ref_cache
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.role_management.contractorUserType import ContractorUserType
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.staffUserType import StaffUserType


def _client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _session_payload(request):
    """Decode the caller's bearer token for logout/heartbeat.

    Signature is verified but expiry is not: an expired token must still be
    able to close its own session.
    """
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = "".join(auth.split(" ", 1)[1].split())
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except jwt.InvalidTokenError:
        return None


def _parse_client_time(value, upper_bound):
    """Parse a client-reported ISO timestamp, never trusting it past now."""
    parsed = parse_datetime(value) if isinstance(value, str) else None
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return min(parsed, upper_bound)


class LoginViewSet(ViewSet):
    permission_classes = [AllowAny]
    throttle_scope = "platform_login"

    def create(self, request):
        login_identifier = request.data.get("username", "").strip()
        requested_module = str(request.data.get("login_type") or "auto").strip().lower()
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
                module_name=requested_module,
                username=login_identifier,
                # Never retain submitted credentials in an audit record.
                password=None,
                ip_address=ip_address or "",
                user_agent=getattr(request, "user_agent", ""),
                success=False,
                reason="Invalid credentials"
            )
            raise

        # Permissions are not returned here — clients fetch them from
        # /login/my-permissions/ right after signing in. The serializer still
        # resolves them, for the mobile App Module gate.
        user = serializer.validated_data["user"]
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
            # *usertype_id fields are plain unique_id strings; resolve the row.
            if user_type == "contractor":
                role_model, role_field = ContractorUserType, "contractorusertype_id"
            elif user_type == "government":
                role_model, role_field = GovernmentStaffUserType, "governmentusertype_id"
            else:
                role_model, role_field = StaffUserType, "staffusertype_id"
            role_type_id = getattr(target, role_field, None) or getattr(user, role_field, None)
            role_type = ref_cache.get(role_model, role_type_id) if role_type_id else None

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
            panchayat_id = getattr(leader_source, "panchayat_id", None)
            panchayat = ref_cache.get(Panchayat, panchayat_id) if panchayat_id else None
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
            district_id = getattr(leader_source, "district_id", None)
            district = ref_cache.get(District, district_id) if district_id else None
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
            state_id = getattr(leader_source, "state_id", None)
            state = ref_cache.get(State, state_id) if state_id else None
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
        access["emp_id"] = emp_id
        access["employee_id"] = employee_id

        iat = access["iat"]
        exp = access["exp"]

        access["valid_seconds"] = exp - iat
        access["valid_hours"] = round((exp - iat) / 3600, 2)
        access["valid_days"] = round((exp - iat) / 86400, 4)

        # Browser logins get an idle limit; the mobile app (`client:
        # "mobile"`) keeps its long-lived session.
        session_idle_timeout = (
            None if is_mobile_client(request.data) else idle_timeout_seconds()
        )
        login_audit_id = generate_login_id()
        stamp_session_claims(access, login_audit_id, session_idle_timeout)

        token = str(access)

        # -------------------------
        # REFRESH TOKEN
        # -------------------------
        # Carries the same identity claims as the access token so
        # refresh_token_viewset.py can mint a fresh access token from it
        # alone, without re-hitting the DB or re-resolving which model
        # (Staffcreation/CustomerCreation/leader/platform) the user came from.
        refresh = RefreshToken.for_user(user)
        refresh["unique_id"] = user_unique_id
        refresh["user_type"] = user_type
        refresh["name"] = name
        refresh["role"] = role
        refresh["email"] = email
        refresh["staff_config_name"] = staff_config_name
        refresh["emp_id"] = emp_id
        refresh["employee_id"] = employee_id
        # Same session claims, so a refreshed access token stays tied to
        # this login row (refresh_token_viewset.py copies them across).
        stamp_session_claims(refresh, login_audit_id, session_idle_timeout)
        refresh_token = str(refresh)

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
            unique_id=login_audit_id,
            user_unique_id=user_unique_id,
            module_name=user_type,
            username=login_identifier,
            # Authentication success is auditable without storing a secret.
            password=None,
            ip_address=ip_address or "",
            user_agent=getattr(request, "user_agent", ""),
            success=True,
            reason=None,
            idle_timeout_seconds=session_idle_timeout,
            last_activity_at=timezone.now(),
        )

        close_stale_sessions_throttled()

        return Response(
            {
                "unique_id": user_unique_id,
                "user_type": user_type,
                "name": name,
                "role": role,
                "is_admin": is_admin_portal_role(role),
                "staff_config_name": staff_config_name,
                "access_token": token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": exp - iat,
                "login_audit_id": login_audit_id,
                "idle_timeout_seconds": session_idle_timeout,
                "email": email,
                "emp_id": emp_id,
                "employee_id": employee_id,
                "profile": profile_payload,
                "password_expired": password_expired,
            },
            status=status.HTTP_200_OK
        )

    # ----------------------------------------------------------
    # POST /api/v1/login/login-user/logout/
    # ----------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path="logout",
        authentication_classes=[],
        throttle_scope="login_session",
    )
    def logout(self, request):
        """Close the caller's login session on its LoginAudit row.

        Body: {"reason": "manual" | "idle_timeout" | "token_expired",
               "last_activity_at": ISO timestamp (idle_timeout only)}
        For an idle timeout the logout is stamped at last activity + idle
        limit, i.e. when the auto-logout actually fell due.
        """
        payload = _session_payload(request)
        audit_id = resolve_login_audit_id(payload) if payload else None
        if not audit_id:
            # No token, or no matching login row: nothing to close, and the
            # client clears its own storage regardless.
            return Response({"detail": "No active session"}, status=status.HTTP_200_OK)

        reason = request.data.get("reason") or LoginAudit.LOGOUT_MANUAL
        if reason not in dict(LoginAudit.LOGOUT_TYPE_CHOICES):
            reason = LoginAudit.LOGOUT_MANUAL

        now = timezone.now()
        logout_at = now
        if reason == LoginAudit.LOGOUT_IDLE_TIMEOUT and payload.get("idle_timeout"):
            last_activity = _parse_client_time(request.data.get("last_activity_at"), now)
            if last_activity:
                logout_at = min(
                    last_activity + timedelta(seconds=payload["idle_timeout"]),
                    now,
                )

        audit = close_session(audit_id, reason, logout_at)
        if audit is None:
            return Response({"detail": "No active session"}, status=status.HTTP_200_OK)

        return Response(
            {
                "login_audit_id": audit.unique_id,
                "login_at": audit.timestamp,
                "logout_at": audit.logout_at,
                "logout_type": audit.logout_type,
                "session_duration_seconds": audit.session_duration_seconds,
                "used_hours": audit.used_hours,
            },
            status=status.HTTP_200_OK,
        )

    # ----------------------------------------------------------
    # POST /api/v1/login/login-user/heartbeat/
    # ----------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path="heartbeat",
        authentication_classes=[],
        throttle_scope="login_session",
    )
    def heartbeat(self, request):
        """Record user activity so the server-side idle check stays in step
        with the browser. Sent only while the user is actually interacting
        (background polling does not count as activity)."""
        payload = _session_payload(request)
        audit_id = (payload or {}).get("login_audit_id")
        if not audit_id:
            return Response(status=status.HTTP_204_NO_CONTENT)

        ended = validate_session(payload)
        if ended:
            return Response({"detail": ended}, status=status.HTTP_401_UNAUTHORIZED)

        now = timezone.now()
        touch_session(
            audit_id,
            _parse_client_time(request.data.get("last_activity_at"), now) or now,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
