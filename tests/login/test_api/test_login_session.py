"""
Login session tracking: logout / idle timeout stamped on LoginAudit.
"""
from datetime import timedelta

import pytest
from django.core.cache import cache, caches
from django.utils import timezone
from rest_framework.test import APIClient

from app.models.superadmin.audits.login_audit import LoginAudit
from app.models.superadmin_masters.auth_user import User
from app.services.login_session import close_stale_sessions, session_lifetime

LOGIN_URL = "/api/v1/login/login-user/"
LOGOUT_URL = "/api/v1/login/login-user/logout/"
HEARTBEAT_URL = "/api/v1/login/login-user/heartbeat/"
REFRESH_URL = "/api/v1/login/refresh-token/"
PROTECTED_URL = "/api/v1/audits/login-audit/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def _skip_app_module_gate(monkeypatch):
    # A mobile sign-in also needs an App Module grant; that gate is covered
    # elsewhere, these tests only care how the session is tracked.
    from app.serializers.login.login_serializer import LoginSerializer
    monkeypatch.setattr(LoginSerializer, "_is_mobile_client", staticmethod(lambda attrs: False))


def _login(api_client, client=None):
    User.objects.create_superuser(
        username="session_admin", password="Session@123", unique_id="U-SESSION-01",
    )
    body = {"username": "session_admin", "password": "Session@123"}
    if client:
        body["client"] = client
    resp = api_client.post(LOGIN_URL, body, format="json")
    assert resp.status_code == 200, resp.data
    return resp.data


def _auth(token):
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    caches["app_cache"].clear()
    yield
    cache.clear()
    caches["app_cache"].clear()


@pytest.mark.django_db
class TestLoginSession:
    def test_browser_login_opens_session_with_idle_limit(self, api_client, settings):
        data = _login(api_client)
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        assert audit.success is True
        assert audit.idle_timeout_seconds == settings.LOGIN_IDLE_TIMEOUT_SECONDS
        assert data["idle_timeout_seconds"] == settings.LOGIN_IDLE_TIMEOUT_SECONDS
        assert audit.logout_at is None

    def test_superuser_login_reports_is_admin(self, api_client):
        data = _login(api_client)
        assert data["role"] == "superadmin"
        assert data["is_admin"] is True

    def test_mobile_login_has_no_idle_limit(self, api_client):
        data = _login(api_client, client="mobile")
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        assert audit.idle_timeout_seconds is None

    def test_manual_logout_stamps_time_and_used_hours(self, api_client):
        data = _login(api_client)
        LoginAudit.objects.filter(pk=data["login_audit_id"]).update(
            timestamp=timezone.now() - timedelta(hours=1, minutes=30),
            last_activity_at=timezone.now(),
        )
        resp = api_client.post(
            LOGOUT_URL, {"reason": "manual"}, format="json", **_auth(data["access_token"])
        )
        assert resp.status_code == 200
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        assert audit.logout_type == LoginAudit.LOGOUT_MANUAL
        assert audit.logout_at is not None
        assert 5390 <= audit.session_duration_seconds <= 5410
        assert audit.used_hours.startswith("01:30")

    def test_logged_out_token_is_rejected(self, api_client):
        data = _login(api_client)
        token = data["access_token"]
        assert api_client.get(PROTECTED_URL, **_auth(token)).status_code == 200
        api_client.post(LOGOUT_URL, {}, format="json", **_auth(token))
        resp = api_client.get(PROTECTED_URL, **_auth(token))
        assert resp.status_code == 401

    def test_logout_is_idempotent(self, api_client):
        data = _login(api_client)
        token = data["access_token"]
        api_client.post(LOGOUT_URL, {"reason": "manual"}, format="json", **_auth(token))
        first = LoginAudit.objects.get(pk=data["login_audit_id"]).logout_at
        api_client.post(LOGOUT_URL, {"reason": "idle_timeout"}, format="json", **_auth(token))
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        assert audit.logout_at == first
        assert audit.logout_type == LoginAudit.LOGOUT_MANUAL

    def test_idle_logout_stamped_at_idle_deadline(self, api_client, settings):
        data = _login(api_client)
        login_at = timezone.now() - timedelta(hours=2)
        last_activity = login_at + timedelta(minutes=30)
        LoginAudit.objects.filter(pk=data["login_audit_id"]).update(timestamp=login_at)
        resp = api_client.post(
            LOGOUT_URL,
            {"reason": "idle_timeout", "last_activity_at": last_activity.isoformat()},
            format="json",
            **_auth(data["access_token"]),
        )
        assert resp.status_code == 200
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        expected = last_activity + timedelta(seconds=settings.LOGIN_IDLE_TIMEOUT_SECONDS)
        assert audit.logout_type == LoginAudit.LOGOUT_IDLE_TIMEOUT
        assert abs((audit.logout_at - expected).total_seconds()) < 1

    def test_server_rejects_idle_session(self, api_client, settings):
        data = _login(api_client)
        stale = timezone.now() - timedelta(seconds=settings.LOGIN_IDLE_TIMEOUT_SECONDS + 600)
        LoginAudit.objects.filter(pk=data["login_audit_id"]).update(
            timestamp=stale, last_activity_at=stale
        )
        resp = api_client.get(PROTECTED_URL, **_auth(data["access_token"]))
        assert resp.status_code == 401
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        assert audit.logout_type == LoginAudit.LOGOUT_IDLE_TIMEOUT

    def test_heartbeat_updates_last_activity(self, api_client):
        data = _login(api_client)
        old = timezone.now() - timedelta(minutes=10)
        LoginAudit.objects.filter(pk=data["login_audit_id"]).update(last_activity_at=old)
        resp = api_client.post(HEARTBEAT_URL, {}, format="json", **_auth(data["access_token"]))
        assert resp.status_code == 204
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        assert audit.last_activity_at > old

    def test_heartbeat_after_logout_is_401(self, api_client):
        data = _login(api_client)
        token = data["access_token"]
        api_client.post(LOGOUT_URL, {}, format="json", **_auth(token))
        resp = api_client.post(HEARTBEAT_URL, {}, format="json", **_auth(token))
        assert resp.status_code == 401

    def test_sweep_closes_abandoned_sessions(self, api_client, settings):
        data = _login(api_client)
        stale = timezone.now() - timedelta(hours=3)
        LoginAudit.objects.filter(pk=data["login_audit_id"]).update(
            timestamp=stale, last_activity_at=stale
        )
        assert close_stale_sessions() == 1
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        assert audit.logout_type == LoginAudit.LOGOUT_IDLE_TIMEOUT
        assert audit.session_duration_seconds == settings.LOGIN_IDLE_TIMEOUT_SECONDS

    def test_login_audit_list_exposes_session_fields(self, api_client):
        data = _login(api_client)
        resp = api_client.get(PROTECTED_URL, **_auth(data["access_token"]))
        rows = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        row = next(r for r in rows if r["unique_id"] == data["login_audit_id"])
        assert row["session_state"] == "active"
        for key in ("logout_at", "logout_type", "used_hours", "last_activity_at"):
            assert key in row


@pytest.mark.django_db
class TestRefreshKeepsSession:
    def test_refreshed_token_stays_on_the_same_session(self, api_client):
        data = _login(api_client)
        resp = api_client.post(REFRESH_URL, {"refresh": data["refresh_token"]}, format="json")
        assert resp.status_code == 200
        new_token = resp.data["access_token"]
        api_client.post(LOGOUT_URL, {"reason": "manual"}, format="json", **_auth(new_token))
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        assert audit.logout_type == LoginAudit.LOGOUT_MANUAL

    def test_ended_session_cannot_be_refreshed(self, api_client):
        data = _login(api_client)
        api_client.post(LOGOUT_URL, {}, format="json", **_auth(data["access_token"]))
        resp = api_client.post(REFRESH_URL, {"refresh": data["refresh_token"]}, format="json")
        assert resp.status_code == 401


@pytest.mark.django_db
class TestLegacySessions:
    """Logins made before session tracking (token without login_audit_id)."""

    def _legacy_token(self, audit):
        from rest_framework_simplejwt.tokens import AccessToken
        user = User.objects.get(unique_id=audit.user_unique_id)
        token = AccessToken.for_user(user)
        token["unique_id"] = user.unique_id
        token["iat"] = int(audit.timestamp.timestamp())
        return str(token)

    def test_logout_links_legacy_token_to_its_login_row(self, api_client):
        data = _login(api_client, client="mobile")
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        token = self._legacy_token(audit)
        resp = api_client.post(LOGOUT_URL, {"reason": "manual"}, format="json", **_auth(token))
        assert resp.status_code == 200
        audit.refresh_from_db()
        assert audit.logout_type == LoginAudit.LOGOUT_MANUAL
        assert audit.used_hours is not None

    def test_sweep_expires_rows_after_session_lifetime(self, api_client):
        data = _login(api_client, client="mobile")
        lifetime = session_lifetime()
        login_at = timezone.now() - lifetime - timedelta(days=1)
        LoginAudit.objects.filter(pk=data["login_audit_id"]).update(timestamp=login_at)
        assert close_stale_sessions() == 1
        audit = LoginAudit.objects.get(pk=data["login_audit_id"])
        assert audit.logout_type == LoginAudit.LOGOUT_TOKEN_EXPIRED
        assert audit.logout_at == login_at + lifetime

    def test_sweep_leaves_live_mobile_session_open(self, api_client):
        data = _login(api_client, client="mobile")
        assert close_stale_sessions() == 0
        assert LoginAudit.objects.get(pk=data["login_audit_id"]).logout_at is None


@pytest.mark.django_db
def test_audit_list_filters_by_session_state(api_client):
    data = _login(api_client)
    token = data["access_token"]
    LoginAudit.objects.create(username="bad", success=False, reason="Invalid credentials")
    other = LoginAudit.objects.create(user_unique_id="U-X", username="x", success=True)
    LoginAudit.objects.filter(pk=other.pk).update(
        logout_at=timezone.now(), logout_type=LoginAudit.LOGOUT_MANUAL
    )

    def ids(state):
        resp = api_client.get(PROTECTED_URL, {"session_state": state}, **_auth(token))
        rows = resp.data["results"] if isinstance(resp.data, dict) else resp.data
        return {r["unique_id"] for r in rows}

    assert data["login_audit_id"] in ids("active")
    assert ids("manual") == {other.pk}
    assert ids("idle_timeout") == set()
    assert data["login_audit_id"] not in ids("failed")
