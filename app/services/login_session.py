"""Login session lifecycle on top of LoginAudit.

Every successful login row is also the session record. The access and
refresh tokens carry the row id as `login_audit_id`; this module stamps
activity, logout time, logout type and used duration back onto that row,
and rejects tokens whose session has already ended (manual logout or idle
timeout) — including refresh tokens, so an ended session cannot be renewed.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from app.models.superadmin.audits.login_audit import LoginAudit


# Requests within this window reuse the cached session state instead of
# hitting the DB.
_STATE_TTL_SECONDS = 60
# Tolerance for heartbeat delay before the server itself declares a session
# idle; the browser normally logs out first, exactly at the timeout.
_IDLE_GRACE_SECONDS = 120

SESSION_CLAIMS = ("login_audit_id", "idle_timeout")

SESSION_ENDED_MESSAGES = {
    LoginAudit.LOGOUT_MANUAL: "Session has been logged out",
    LoginAudit.LOGOUT_IDLE_TIMEOUT: "Session expired due to inactivity",
    LoginAudit.LOGOUT_TOKEN_EXPIRED: "Session expired",
}


def _cache_key(audit_id):
    return f"login-session:{audit_id}"


def idle_timeout_seconds():
    return getattr(settings, "LOGIN_IDLE_TIMEOUT_SECONDS", 40 * 60)


def session_lifetime():
    """How long a session can live without a fresh login: the refresh token
    keeps renewing the access token until it expires itself."""
    jwt_settings = settings.SIMPLE_JWT
    return jwt_settings.get("REFRESH_TOKEN_LIFETIME") or jwt_settings["ACCESS_TOKEN_LIFETIME"]


def stamp_session_claims(token, audit_id, idle_timeout):
    """Attach the session claims to a freshly minted access/refresh token."""
    token["login_audit_id"] = audit_id
    if idle_timeout:
        token["idle_timeout"] = idle_timeout


def close_session(audit_id, logout_type, logout_at=None):
    """Stamp logout time/type/duration on the login row. Idempotent: an
    already-closed session keeps its original logout. Returns the row."""
    audit = LoginAudit.objects.filter(pk=audit_id, success=True).first()
    if audit is None:
        return None
    if audit.logout_at is None:
        logout_at = logout_at or timezone.now()
        if logout_at < audit.timestamp:
            logout_at = audit.timestamp
        audit.logout_at = logout_at
        audit.logout_type = logout_type
        audit.session_duration_seconds = int(
            (logout_at - audit.timestamp).total_seconds()
        )
        audit.save(
            update_fields=["logout_at", "logout_type", "session_duration_seconds"]
        )
    cache.delete(_cache_key(audit_id))
    return audit


def touch_session(audit_id, at=None):
    """Record user activity (heartbeat) on an open session."""
    at = at or timezone.now()
    LoginAudit.objects.filter(pk=audit_id, logout_at__isnull=True).update(
        last_activity_at=at
    )
    cache.delete(_cache_key(audit_id))


def resolve_login_audit_id(payload):
    """The session row a token belongs to.

    Tokens minted before session tracking carry no `login_audit_id`; their
    row is the user's successful login stamped when the token was issued.
    """
    audit_id = payload.get("login_audit_id")
    if audit_id:
        return audit_id
    user_unique_id = payload.get("unique_id")
    iat = payload.get("iat")
    if not user_unique_id or not iat:
        return None
    issued_at = datetime.fromtimestamp(iat, tz=dt_timezone.utc)
    return (
        LoginAudit.objects.filter(
            user_unique_id=user_unique_id,
            success=True,
            timestamp__gte=issued_at - timedelta(seconds=5),
            timestamp__lte=issued_at + timedelta(seconds=60),
        )
        .order_by("timestamp")
        .values_list("unique_id", flat=True)
        .first()
    )


def _load_state(audit_id):
    row = (
        LoginAudit.objects.filter(pk=audit_id)
        .values("logout_type", "logout_at", "last_activity_at", "timestamp")
        .first()
    )
    if row is None:
        return None
    last = row["last_activity_at"] or row["timestamp"]
    return {
        "closed_as": row["logout_type"] if row["logout_at"] else None,
        "last_activity": last.timestamp(),
        "loaded_at": timezone.now().timestamp(),
    }


def validate_session(payload):
    """Return an error message if the token's session has ended, else None.

    Tokens minted before session tracking (no `login_audit_id`) pass
    through unchanged.
    """
    audit_id = payload.get("login_audit_id")
    if not audit_id:
        return None

    now_ts = timezone.now().timestamp()
    key = _cache_key(audit_id)
    state = cache.get(key)
    if state is None or now_ts - state["loaded_at"] > _STATE_TTL_SECONDS:
        state = _load_state(audit_id)
        if state is None:
            return None
        cache.set(key, state, _STATE_TTL_SECONDS)

    if state["closed_as"]:
        return SESSION_ENDED_MESSAGES.get(state["closed_as"], "Session has ended")

    idle_timeout = payload.get("idle_timeout")
    if idle_timeout and now_ts - state["last_activity"] > idle_timeout + _IDLE_GRACE_SECONDS:
        # The browser never reported activity in time (tab closed, machine
        # asleep, ...): the session ended when the idle limit ran out.
        logout_at = datetime.fromtimestamp(
            state["last_activity"] + idle_timeout, tz=dt_timezone.utc
        )
        close_session(audit_id, LoginAudit.LOGOUT_IDLE_TIMEOUT, logout_at)
        return SESSION_ENDED_MESSAGES[LoginAudit.LOGOUT_IDLE_TIMEOUT]

    return None


_SWEEP_THROTTLE_KEY = "login-session:last-sweep"
_SWEEP_THROTTLE_SECONDS = 60


def close_stale_sessions(now=None):
    """Close sessions nobody came back to log out of: web sessions past
    their idle limit, and any session (web, mobile, or from before session
    tracking) that can no longer be renewed. Returns the number closed."""
    now = now or timezone.now()
    lifetime = session_lifetime()
    idle_cutoff = now - timedelta(seconds=_IDLE_GRACE_SECONDS)
    closed = 0

    # Only rows that can possibly be stale: past the session lifetime, or an
    # idle-limited session (checked row by row below).
    candidates = LoginAudit.objects.filter(
        success=True, logout_at__isnull=True
    ).filter(
        models.Q(timestamp__lt=now - lifetime)
        | models.Q(idle_timeout_seconds__isnull=False)
    ).only("unique_id", "timestamp", "last_activity_at", "idle_timeout_seconds")

    for audit in candidates.iterator():
        expiry = audit.timestamp + lifetime
        idle_deadline = None
        if audit.idle_timeout_seconds:
            last = audit.last_activity_at or audit.timestamp
            idle_deadline = last + timedelta(seconds=audit.idle_timeout_seconds)
        if idle_deadline and idle_deadline <= expiry and idle_deadline < idle_cutoff:
            close_session(audit.unique_id, LoginAudit.LOGOUT_IDLE_TIMEOUT, idle_deadline)
            closed += 1
        elif expiry < now:
            close_session(audit.unique_id, LoginAudit.LOGOUT_TOKEN_EXPIRED, expiry)
            closed += 1
    return closed


def close_stale_sessions_throttled():
    """close_stale_sessions at most once a minute — cheap enough to call
    from request paths so the audit stays correct without the beat task."""
    if not cache.add(_SWEEP_THROTTLE_KEY, True, _SWEEP_THROTTLE_SECONDS):
        return 0
    return close_stale_sessions()
