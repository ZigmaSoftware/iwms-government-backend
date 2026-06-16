"""
Unit tests for LoginViewSet and PermissionViewSet.

Coverage targets:
  - login_viewset.py  : all branches (platform/staff/customer/contractor, company resolution)
  - permission_viewset.py : all branches (_resolve_staff_user, _format_permissions,
                            _get_all_permissions, non-superuser paths)
"""
import pytest
from unittest.mock import patch, MagicMock

LOGIN_BASE = "/api/v1/login/login-user/"
PERMISSIONS_BASE = "/api/v1/login/my-permissions/"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _make_platform_user(db):
    from app.models.superadmin_masters.auth_user import User
    return User.objects.create_superuser(
        username="platform_admin",
        password="Platform@123",
        unique_id="U-PLATFORM-01",
    )


def _make_non_superuser_token(db, username, unique_id):
    """Create superuser, downgrade to non-superuser in DB, return JWT string."""
    from app.models.superadmin_masters.auth_user import User
    from rest_framework_simplejwt.tokens import AccessToken
    user = User.objects.create_superuser(
        username=username, password="Pass@1234", unique_id=unique_id,
    )
    user.is_superuser = False
    user.save()
    token = AccessToken.for_user(user)
    token["unique_id"] = user.unique_id
    return str(token)


def _mock_serializer(user, user_type, profile_object=None, extra=None):
    """Build (MockSerializerClass, configured mock instance) for patching."""
    validated = {
        "user": user,
        "permissions": {},
        "permission_details": {},
        "column_permissions": {},
        "user_type": user_type,
        "profile_object": profile_object,
        "company_unique_id": None,
        "staffusertype_id": None,
        "contractorusertype_id": None,
        "projects": [],
    }
    if extra:
        validated.update(extra)
    mock_inst = MagicMock()
    mock_inst.is_valid.return_value = True
    mock_inst.validated_data = validated
    return mock_inst


# ──────────────────────────────────────────────────────────────────────────────
# LOGIN FAILURE PATHS  (regression)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginFailure:
    def test_missing_credentials_returns_error(self, api_client):
        resp = api_client.post(LOGIN_BASE, {}, format="json")
        assert resp.status_code in (400, 401)

    def test_wrong_password_returns_error(self, api_client):
        resp = api_client.post(
            LOGIN_BASE, {"username": "nobody", "password": "wrong"}, format="json"
        )
        assert resp.status_code in (400, 401)

    def test_failure_creates_login_audit(self, api_client):
        from app.models.user_creations.loginAudit import LoginAudit
        before = LoginAudit.objects.filter(success=False).count()
        api_client.post(LOGIN_BASE, {"username": "audit_user", "password": "bad"}, format="json")
        after = LoginAudit.objects.filter(success=False).count()
        assert after > before


# ──────────────────────────────────────────────────────────────────────────────
# PLATFORM LOGIN SUCCESS  (lines 65-75, 151-157)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginPlatformSuccess:
    def test_platform_login_returns_200(self, api_client, db):
        _make_platform_user(db)
        resp = api_client.post(
            LOGIN_BASE, {"username": "platform_admin", "password": "Platform@123"}, format="json"
        )
        assert resp.status_code == 200

    def test_platform_login_has_access_token(self, api_client, db):
        _make_platform_user(db)
        resp = api_client.post(
            LOGIN_BASE, {"username": "platform_admin", "password": "Platform@123"}, format="json"
        )
        assert "access_token" in resp.data and resp.data["access_token"] != ""

    def test_platform_login_expected_keys(self, api_client, db):
        _make_platform_user(db)
        resp = api_client.post(
            LOGIN_BASE, {"username": "platform_admin", "password": "Platform@123"}, format="json"
        )
        for key in ("unique_id", "user_type", "name", "role", "permissions",
                    "access_token", "token_type", "expires_in", "profile"):
            assert key in resp.data, f"Missing key: {key}"

    def test_platform_login_user_type_is_platform(self, api_client, db):
        _make_platform_user(db)
        resp = api_client.post(
            LOGIN_BASE, {"username": "platform_admin", "password": "Platform@123"}, format="json"
        )
        assert resp.data["user_type"] == "platform"

    def test_platform_login_role_is_superadmin(self, api_client, db):
        _make_platform_user(db)
        resp = api_client.post(
            LOGIN_BASE, {"username": "platform_admin", "password": "Platform@123"}, format="json"
        )
        assert resp.data["role"] == "superadmin"

    def test_platform_login_profile_keys(self, api_client, db):
        _make_platform_user(db)
        resp = api_client.post(
            LOGIN_BASE, {"username": "platform_admin", "password": "Platform@123"}, format="json"
        )
        profile = resp.data["profile"]
        assert "platform_username" in profile
        assert profile["is_superuser"] is True

    def test_platform_login_success_audit_created(self, api_client, db):
        from app.models.user_creations.loginAudit import LoginAudit
        _make_platform_user(db)
        before = LoginAudit.objects.filter(success=True).count()
        api_client.post(
            LOGIN_BASE, {"username": "platform_admin", "password": "Platform@123"}, format="json"
        )
        after = LoginAudit.objects.filter(success=True).count()
        assert after > before

    def test_platform_login_token_type_is_bearer(self, api_client, db):
        _make_platform_user(db)
        resp = api_client.post(
            LOGIN_BASE, {"username": "platform_admin", "password": "Platform@123"}, format="json"
        )
        assert resp.data["token_type"] == "Bearer"

    def test_platform_login_expires_in_positive(self, api_client, db):
        _make_platform_user(db)
        resp = api_client.post(
            LOGIN_BASE, {"username": "platform_admin", "password": "Platform@123"}, format="json"
        )
        assert resp.data["expires_in"] > 0


# ──────────────────────────────────────────────────────────────────────────────
# LOGIN TYPE PARAM
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginTypeParam:
    def test_login_type_platform_explicit(self, api_client, db):
        _make_platform_user(db)
        resp = api_client.post(
            LOGIN_BASE,
            {"username": "platform_admin", "password": "Platform@123", "login_type": "platform"},
            format="json",
        )
        assert resp.status_code == 200

    def test_login_type_wrong_rejects(self, api_client):
        resp = api_client.post(
            LOGIN_BASE, {"username": "nobody", "password": "x", "login_type": "platform"}, format="json"
        )
        assert resp.status_code in (400, 401)


# ──────────────────────────────────────────────────────────────────────────────
# STAFF BRANCH  (lines 76-99, 131-141)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginStaffBranch:
    def _user(self, db, suffix="01"):
        from app.models.superadmin_masters.auth_user import User
        return User.objects.create_superuser(
            username=f"staff_u{suffix}", password="P@ss123", unique_id=f"U-STAFF-{suffix}"
        )

    def test_staff_login_with_encrypted_password_returns_200(
        self,
        api_client,
        company,
        project,
        user_type,
    ):
        from app.models.role_assigns.staffUserType import StaffUserType
        from app.models.user_creations.staffcreation import Staffcreation
        from app.utils.password_encryption import encrypt_password

        staff_user_type = StaffUserType.objects.create(
            usertype_id=user_type,
            name="company_admin",
            company_id=company,
            project_id=project,
        )
        Staffcreation.objects.create(
            username="admin",
            password=encrypt_password("12345678"),
            employee_name="admin",
            company_id=company,
            project_id=project,
            user_type_id=user_type,
            staffusertype_id=staff_user_type,
            approval_status=Staffcreation.APPROVAL_APPROVED,
            login_enabled=True,
        )

        resp = api_client.post(
            LOGIN_BASE,
            {"username": "admin", "password": "12345678"},
            format="json",
        )

        assert resp.status_code == 200
        assert resp.data["user_type"] == "staff"

    def test_staff_login_returns_200(self, api_client, db):
        user = self._user(db, "01")
        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "staff")
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        assert resp.status_code == 200
        assert resp.data["user_type"] == "staff"

    def test_staff_login_profile_has_staff_fields(self, api_client, db):
        user = self._user(db, "02")
        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "staff")
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        profile = resp.data["profile"]
        assert "staff_unique_id" in profile
        assert "employee_id" in profile
        assert "staffusertype_unique_id" in profile

    def test_staff_login_role_from_role_type(self, api_client, db):
        """Lines 85-86: role resolved from staffusertype_id.name."""
        user = self._user(db, "03")
        mock_role = MagicMock()
        mock_role.name = "field_operator"
        mock_profile = MagicMock()
        mock_profile.employee_name = "Field Worker"
        mock_profile.staffusertype_id = mock_role
        mock_profile.contractorusertype_id = None
        mock_profile.company_id = None
        mock_profile.staff_unique_id = "STAFF-FW-01"
        mock_profile.emp_id = None
        mock_profile.personal_details = None

        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "staff", profile_object=mock_profile)
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        assert resp.status_code == 200
        assert resp.data["role"] == "field_operator"

    def test_staff_login_personal_details_email(self, api_client, db):
        """Line 89-90: email from personal_details.contact_email."""
        user = self._user(db, "04")
        mock_personal = MagicMock()
        mock_personal.contact_email = "worker@test.com"
        mock_profile = MagicMock()
        mock_profile.employee_name = "Worker"
        mock_profile.staffusertype_id = None
        mock_profile.contractorusertype_id = None
        mock_profile.company_id = None
        mock_profile.staff_unique_id = None
        mock_profile.emp_id = None
        mock_profile.personal_details = mock_personal

        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "staff", profile_object=mock_profile)
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        assert resp.status_code == 200
        assert resp.data.get("email") == "worker@test.com"


# ──────────────────────────────────────────────────────────────────────────────
# CUSTOMER BRANCH  (lines 60-64, 142-150)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginCustomerBranch:
    def _user(self, db, suffix="01"):
        from app.models.superadmin_masters.auth_user import User
        return User.objects.create_superuser(
            username=f"cust_u{suffix}", password="P@ss123", unique_id=f"U-CUST-{suffix}"
        )

    def test_customer_login_returns_200(self, api_client, db):
        user = self._user(db, "01")
        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "customer")
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        assert resp.status_code == 200
        assert resp.data["user_type"] == "customer"
        assert resp.data["role"] == "customer"

    def test_customer_login_profile_has_customer_fields(self, api_client, db):
        """Lines 142-150: customer profile_payload fields."""
        user = self._user(db, "02")
        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "customer")
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        profile = resp.data["profile"]
        assert "customer_unique_id" in profile
        assert "customer_name" in profile
        assert "contact_no" in profile


# ──────────────────────────────────────────────────────────────────────────────
# CONTRACTOR BRANCH  (lines 76-80, 158-168)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginContractorBranch:
    def _user(self, db, suffix="01"):
        from app.models.superadmin_masters.auth_user import User
        return User.objects.create_superuser(
            username=f"contr_u{suffix}", password="P@ss123", unique_id=f"U-CONTR-{suffix}"
        )

    def test_contractor_login_returns_200(self, api_client, db):
        user = self._user(db, "01")
        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "contractor")
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        assert resp.status_code == 200
        assert resp.data["user_type"] == "contractor"

    def test_contractor_login_profile_has_contractor_fields(self, api_client, db):
        """Lines 158-168: contractor profile_payload fields."""
        user = self._user(db, "02")
        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "contractor")
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        profile = resp.data["profile"]
        assert "contractorusertype_unique_id" in profile
        assert "emp_id" in profile


# ──────────────────────────────────────────────────────────────────────────────
# LOGIN — pk fallback unique_id  (line 107)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginPkFallback:
    def test_unique_id_falls_back_to_pk(self, api_client, db):
        """Line 107: user has no unique_id/staff_unique_id → str(user.pk) used."""
        from app.models.superadmin_masters.auth_user import User
        real_user = User.objects.create_superuser(
            username="fallback_u", password="P@ss123", unique_id="U-FALLBACK-01"
        )

        class DummyUser:
            unique_id = None
            staff_unique_id = None
            employee_name = None
            username = "fallback_u"
            email = None
            company_id = None
            is_superuser = True

            def __init__(self, pk):
                self.pk = pk

        class FakeAccessToken(dict):
            def __str__(self):
                return "fake.jwt.token"

        mock_user = DummyUser(real_user.pk)

        validated = {
            "user": mock_user, "permissions": {}, "permission_details": {},
            "column_permissions": {}, "user_type": "platform", "profile_object": None,
            "company_unique_id": None, "staffusertype_id": None,
            "contractorusertype_id": None, "projects": [],
        }

        mock_token = FakeAccessToken(iat=1_000_000, exp=1_003_600)

        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer, \
             patch("app.viewsets.login.login_viewset.AccessToken") as MockAT:
            inst = MagicMock()
            inst.is_valid.return_value = True
            inst.validated_data = validated
            MockSer.return_value = inst
            MockAT.for_user.return_value = mock_token

            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        assert resp.status_code == 200
        assert resp.data["unique_id"] == str(real_user.pk)


# ──────────────────────────────────────────────────────────────────────────────
# STAFF — employee_id already set  (branch 93->105: skip derivation)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginStaffEmpIdBranch:
    def test_staff_login_with_emp_id_set(self, api_client, db):
        """Branch 93->105: employee_id is truthy → skip Staffcreation._derive_emp_id."""
        from app.models.superadmin_masters.auth_user import User
        user = User.objects.create_superuser(
            username="staff_empid", password="P@ss123", unique_id="U-EMPID-01"
        )
        mock_profile = MagicMock()
        mock_profile.employee_name = "Worker"
        mock_profile.staffusertype_id = None
        mock_profile.contractorusertype_id = None
        mock_profile.company_id = None
        mock_profile.staff_unique_id = "STAFF-EMP-01"
        mock_profile.emp_id = "EMP-001"       # truthy → skips derivation
        mock_profile.personal_details = None

        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "staff", profile_object=mock_profile)
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        assert resp.status_code == 200
        assert resp.data["employee_id"] == "EMP-001"


# ──────────────────────────────────────────────────────────────────────────────
# LOGIN — UNKNOWN USER TYPE fallthrough  (branches 76->105, 158->170)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginUnknownUserType:
    def test_unknown_user_type_still_returns_200(self, api_client, db):
        """Branches 76->105 and 158->170: user_type not in known set → fallthrough."""
        from app.models.superadmin_masters.auth_user import User
        user = User.objects.create_superuser(
            username="unknown_u", password="P@ss123", unique_id="U-UNK-01"
        )
        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "unknown_type")
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        assert resp.status_code == 200
        assert resp.data["user_type"] == "unknown_type"


# ──────────────────────────────────────────────────────────────────────────────
# COMPANY RESOLUTION FROM PROFILE  (lines 110-117)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginCompanyResolution:
    def test_company_from_profile_object(self, api_client, db):
        """Lines 110-117: company resolved from profile_object.company_id."""
        from app.models.superadmin_masters.auth_user import User
        user = User.objects.create_superuser(
            username="comp_u", password="P@ss123", unique_id="U-COMP-01"
        )
        mock_company = MagicMock()
        mock_company.name = "Test Company"
        mock_company.unique_id = "COMP-001"

        mock_profile = MagicMock()
        mock_profile.company_id = mock_company
        mock_profile.employee_name = "Emp"
        mock_profile.staffusertype_id = None
        mock_profile.contractorusertype_id = None
        mock_profile.staff_unique_id = None
        mock_profile.emp_id = None
        mock_profile.personal_details = None

        with patch("app.viewsets.login.login_viewset.LoginSerializer") as MockSer:
            MockSer.return_value = _mock_serializer(user, "staff", profile_object=mock_profile)
            resp = api_client.post(LOGIN_BASE, {"username": "x", "password": "y"}, format="json")
        assert resp.status_code == 200
        assert resp.data["company_name"] == "Test Company"
        assert resp.data["company_unique_id"] == "COMP-001"


# ──────────────────────────────────────────────────────────────────────────────
# PERMISSION VIEWSET — SUPERADMIN
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPermissionViewSetSuperadmin:
    def test_superadmin_gets_200(self, auth_client):
        resp = auth_client.get(PERMISSIONS_BASE)
        assert resp.status_code == 200

    def test_superadmin_response_has_required_keys(self, auth_client):
        resp = auth_client.get(PERMISSIONS_BASE)
        for key in ("permissions", "permission_details", "column_permissions", "timestamp", "source"):
            assert key in resp.data

    def test_superadmin_source_is_database(self, auth_client):
        resp = auth_client.get(PERMISSIONS_BASE)
        assert resp.data["source"] == "database"


@pytest.mark.django_db
class TestPermissionViewSetUnauthenticated:
    def test_unauthenticated_returns_401_or_403(self, api_client):
        resp = api_client.get(PERMISSIONS_BASE)
        assert resp.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────────────────────
# PERMISSION VIEWSET — NON-SUPERUSER PATHS  (lines 169-234)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPermissionViewSetNonSuperuserPaths:
    """
    Uses create_superuser + is_superuser=False to exercise the non-superuser
    branches in _resolve_permissions_for_user, _resolve_permission_details_for_user,
    and _resolve_column_permissions_for_user.
    """

    def test_no_staff_returns_empty(self, api_client, db):
        """Lines 169-171: _resolve_staff_user returns None → {}."""
        token = _make_non_superuser_token(db, "nsup1", "U-NS-01")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        with patch(
            "app.viewsets.login.permission_viewset.PermissionViewSet._resolve_staff_user",
            return_value=None,
        ):
            resp = api_client.get(PERMISSIONS_BASE)
        assert resp.status_code == 200
        assert resp.data["permissions"] == {}
        assert resp.data["permission_details"] == {}
        assert resp.data["column_permissions"] == {}

    def test_staff_without_company_returns_empty(self, api_client, db):
        """Lines 174-180: staff found but company_id is None → {}."""
        token = _make_non_superuser_token(db, "nsup2", "U-NS-02")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        mock_staff = MagicMock()
        mock_staff.company_id = None
        mock_staff.user_type_id = None
        with patch(
            "app.viewsets.login.permission_viewset.PermissionViewSet._resolve_staff_user",
            return_value=mock_staff,
        ):
            resp = api_client.get(PERMISSIONS_BASE)
        assert resp.status_code == 200
        assert resp.data["permissions"] == {}

    def test_staff_with_company_and_usertype_calls_format(self, api_client, db):
        """Lines 182-188, 194-211, 217-234: staff has company+usertype → _format_permissions called."""
        token = _make_non_superuser_token(db, "nsup3", "U-NS-03")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        mock_company = MagicMock()
        mock_company.unique_id = "COMP-001"
        mock_usertype = MagicMock()
        mock_usertype.unique_id = "UT-001"

        mock_staff = MagicMock()
        mock_staff.company_id = mock_company
        mock_staff.user_type_id = mock_usertype
        mock_staff.staffusertype_id = None
        mock_staff.contractorusertype_id = None

        with patch(
            "app.viewsets.login.permission_viewset.PermissionViewSet._resolve_staff_user",
            return_value=mock_staff,
        ):
            resp = api_client.get(PERMISSIONS_BASE)
        assert resp.status_code == 200
        assert isinstance(resp.data["permissions"], dict)
        assert isinstance(resp.data["permission_details"], dict)
        assert isinstance(resp.data["column_permissions"], dict)


# ──────────────────────────────────────────────────────────────────────────────
# _resolve_staff_user — direct unit tests  (lines 279-303)
# ──────────────────────────────────────────────────────────────────────────────

class TestResolveStaffUserUnit:
    """Pure unit tests — no HTTP, no DB (except where marked)."""

    @staticmethod
    def _viewset():
        from app.viewsets.login.permission_viewset import PermissionViewSet
        return PermissionViewSet()

    def test_staffcreation_instance_returned_directly(self):
        """Line 279-280: user IS a Staffcreation → returned as-is."""
        from app.models.user_creations.staffcreation import Staffcreation
        vset = self._viewset()
        mock_staff = MagicMock(spec=Staffcreation)
        result = vset._resolve_staff_user(mock_staff)
        assert result is mock_staff

    def test_user_with_staff_attribute_returns_it(self):
        """Lines 283-285: user.staff is set → returned."""
        vset = self._viewset()
        mock_staff_rel = MagicMock()

        class FakeUser:
            staff = mock_staff_rel
            unique_id = None
            staff_unique_id = None

        result = vset._resolve_staff_user(FakeUser())
        assert result is mock_staff_rel

    def test_user_without_unique_id_returns_none(self):
        """Line 291: unique_id attr exists but is None → user_unique_id falsy → None."""
        vset = self._viewset()

        class FakeUser:
            unique_id = None

        result = vset._resolve_staff_user(FakeUser())
        assert result is None

    def test_user_with_no_id_attrs_elif_false_returns_none(self):
        """Branch 292->295: no unique_id AND no staff_unique_id attrs → elif False → None."""
        vset = self._viewset()

        class FakeUser:
            pass  # no unique_id, no staff_unique_id, no staff

        result = vset._resolve_staff_user(FakeUser())
        assert result is None

    @pytest.mark.django_db
    def test_user_with_unique_id_does_db_lookup(self, db):
        """Lines 295-299: unique_id truthy → Staffcreation DB lookup → None (not found)."""
        vset = self._viewset()

        class FakeUser:
            unique_id = "STAFF-NONEXISTENT-999"

        result = vset._resolve_staff_user(FakeUser())
        assert result is None

    def test_db_exception_in_lookup_returns_none(self):
        """Lines 300-301: exception during DB lookup → None."""
        from app.models.user_creations.staffcreation import Staffcreation
        vset = self._viewset()

        class FakeUser:
            unique_id = "STAFF-EXCEPT-001"

        with patch.object(Staffcreation.objects, "filter", side_effect=Exception("DB error")):
            result = vset._resolve_staff_user(FakeUser())
        assert result is None

    @pytest.mark.django_db
    def test_user_with_staff_unique_id_covers_elif_branch(self, db):
        """Lines 292-293: no unique_id attr but has staff_unique_id → DB lookup → None."""
        vset = self._viewset()

        class FakeUser:
            # no unique_id attribute — forces elif branch
            staff_unique_id = "STAFF-NONEXISTENT-ALT"

        result = vset._resolve_staff_user(FakeUser())
        assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# _get_all_permissions — direct unit tests  (lines 240-267)
# ──────────────────────────────────────────────────────────────────────────────

class TestGetAllPermissionsUnit:
    @staticmethod
    def _viewset():
        from app.viewsets.login.permission_viewset import PermissionViewSet
        return PermissionViewSet()

    def _mock_qs(self, items):
        with patch(
            "app.viewsets.login.permission_viewset.CompanyUserScreenPermission.objects"
        ) as mock_objs:
            qs = MagicMock()
            mock_objs.filter.return_value = qs
            qs.select_related.return_value = qs
            qs.order_by.return_value = items
            yield mock_objs

    def test_empty_returns_empty_dict(self):
        vset = self._viewset()
        with patch(
            "app.viewsets.login.permission_viewset.CompanyUserScreenPermission.objects"
        ) as mock_objs:
            qs = MagicMock()
            mock_objs.filter.return_value = qs
            qs.select_related.return_value = qs
            qs.order_by.return_value = []
            result = vset._get_all_permissions()
        assert result == {}

    def test_with_permissions_builds_nested_structure(self):
        """Lines 256-265: loop body, setdefault, append."""
        vset = self._viewset()
        perm = MagicMock()
        perm.mainscreen_id.mainscreen_name = "Assets"
        perm.userscreen_id.userscreen_name = "Bins"
        perm.userscreenaction_id.action_name = "view"

        with patch(
            "app.viewsets.login.permission_viewset.CompanyUserScreenPermission.objects"
        ) as mock_objs:
            qs = MagicMock()
            mock_objs.filter.return_value = qs
            qs.select_related.return_value = qs
            qs.order_by.return_value = [perm]
            result = vset._get_all_permissions()
        assert result == {"Assets": {"Bins": ["view"]}}

    def test_duplicate_action_not_added_twice(self):
        """Line 264: duplicate action_name skipped."""
        vset = self._viewset()

        def _perm():
            p = MagicMock()
            p.mainscreen_id.mainscreen_name = "Module"
            p.userscreen_id.userscreen_name = "Screen"
            p.userscreenaction_id.action_name = "edit"
            return p

        with patch(
            "app.viewsets.login.permission_viewset.CompanyUserScreenPermission.objects"
        ) as mock_objs:
            qs = MagicMock()
            mock_objs.filter.return_value = qs
            qs.select_related.return_value = qs
            qs.order_by.return_value = [_perm(), _perm()]
            result = vset._get_all_permissions()
        assert result["Module"]["Screen"].count("edit") == 1

    def test_multiple_screens_in_same_module(self):
        vset = self._viewset()

        def _perm(screen, action):
            p = MagicMock()
            p.mainscreen_id.mainscreen_name = "Assets"
            p.userscreen_id.userscreen_name = screen
            p.userscreenaction_id.action_name = action
            return p

        with patch(
            "app.viewsets.login.permission_viewset.CompanyUserScreenPermission.objects"
        ) as mock_objs:
            qs = MagicMock()
            mock_objs.filter.return_value = qs
            qs.select_related.return_value = qs
            qs.order_by.return_value = [_perm("Bins", "view"), _perm("Vehicles", "add")]
            result = vset._get_all_permissions()
        assert "Bins" in result["Assets"]
        assert "Vehicles" in result["Assets"]


# ──────────────────────────────────────────────────────────────────────────────
# _format_permissions — direct unit tests  (lines 325-367)
# ──────────────────────────────────────────────────────────────────────────────

class TestFormatPermissionsUnit:
    @staticmethod
    def _viewset():
        from app.viewsets.login.permission_viewset import PermissionViewSet
        return PermissionViewSet()

    def _patch_objs(self, items, extra_filter_return=None):
        """Context manager that patches CompanyUserScreenPermission.objects."""
        import contextlib

        @contextlib.contextmanager
        def _ctx():
            with patch(
                "app.viewsets.login.permission_viewset.CompanyUserScreenPermission.objects"
            ) as mock_objs:
                qs = MagicMock()
                mock_objs.filter.return_value = qs
                qs.select_related.return_value = qs
                qs.filter.return_value = qs
                qs.order_by.return_value = items
                yield mock_objs

        return _ctx()

    def test_no_company_returns_empty(self):
        """Line 325-326: company_unique_id is None → {}."""
        vset = self._viewset()
        result = vset._format_permissions(company_unique_id=None, usertype_unique_id="UT-001")
        assert result == {}

    def test_no_usertype_returns_empty(self):
        """Line 325-326: usertype_unique_id is None → {}."""
        vset = self._viewset()
        result = vset._format_permissions(company_unique_id="COMP-001", usertype_unique_id=None)
        assert result == {}

    def test_with_staffusertype_filter(self):
        """Lines 340-343: staffusertype_unique_id → filter by staffusertype."""
        vset = self._viewset()
        perm = MagicMock()
        perm.mainscreen_id.mainscreen_name = "Assets"
        perm.userscreen_id.userscreen_name = "Bins"
        perm.userscreenaction_id.action_name = "view"

        with self._patch_objs([perm]):
            result = vset._format_permissions(
                company_unique_id="COMP-001",
                usertype_unique_id="UT-001",
                staffusertype_unique_id="SUT-001",
            )
        assert result == {"Assets": {"Bins": ["view"]}}

    def test_with_contractorusertype_filter(self):
        """Lines 344-347: contractorusertype_unique_id → filter by contractorusertype."""
        vset = self._viewset()
        perm = MagicMock()
        perm.mainscreen_id.mainscreen_name = "Reports"
        perm.userscreen_id.userscreen_name = "Daily"
        perm.userscreenaction_id.action_name = "export"

        with self._patch_objs([perm]):
            result = vset._format_permissions(
                company_unique_id="COMP-001",
                usertype_unique_id="UT-001",
                contractorusertype_unique_id="CUT-001",
            )
        assert result == {"Reports": {"Daily": ["export"]}}

    def test_without_any_usertype_uses_isnull_filter(self):
        """Lines 348-352: neither staffusertype nor contractorusertype → isnull filter."""
        vset = self._viewset()
        with self._patch_objs([]):
            result = vset._format_permissions(
                company_unique_id="COMP-001",
                usertype_unique_id="UT-001",
            )
        assert result == {}

    def test_duplicate_action_not_appended(self):
        """Line 364: if action_name not in action_list → not appended again."""
        vset = self._viewset()

        def _perm():
            p = MagicMock()
            p.mainscreen_id.mainscreen_name = "A"
            p.userscreen_id.userscreen_name = "B"
            p.userscreenaction_id.action_name = "view"
            return p

        with self._patch_objs([_perm(), _perm()]):
            result = vset._format_permissions(
                company_unique_id="COMP-001",
                usertype_unique_id="UT-001",
            )
        assert result["A"]["B"].count("view") == 1

    def test_builds_nested_structure(self):
        """Lines 354-366: loop builds module → screen → actions."""
        vset = self._viewset()

        def _perm(module, screen, action):
            p = MagicMock()
            p.mainscreen_id.mainscreen_name = module
            p.userscreen_id.userscreen_name = screen
            p.userscreenaction_id.action_name = action
            return p

        with self._patch_objs([
            _perm("Assets", "Bins", "view"),
            _perm("Assets", "Bins", "add"),
            _perm("Reports", "Summary", "export"),
        ]):
            result = vset._format_permissions(
                company_unique_id="COMP-001",
                usertype_unique_id="UT-001",
            )
        assert set(result["Assets"]["Bins"]) == {"view", "add"}
        assert result["Reports"]["Summary"] == ["export"]
