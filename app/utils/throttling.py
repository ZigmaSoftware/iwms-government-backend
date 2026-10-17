"""
Per-HTTP-method rate limiting on top of DRF's ScopedRateThrottle.

DRF's stock ScopedRateThrottle keys purely on `view.throttle_scope` and
looks up ONE rate string for it in settings.DEFAULT_THROTTLE_RATES, so
GET/POST/PUT/PATCH/DELETE on the same view share one Redis counter and one
limit. MethodScopedRateThrottle is a minimal subclass that adds method
awareness while reusing everything else DRF already does: the same Redis
connection (Django's cache framework, CACHES["default"]), the same
identity resolution (user pk or IP), and the same window/TTL mechanics
(SimpleRateThrottle.allow_request/throttle_success).

An entry in settings.API_THROTTLE_RATES may be either:

  * a plain string, e.g. "5/minute" — applies to every HTTP method,
    identical to today's behaviour. Existing scopes need no changes.

  * a dict of per-method overrides with a required "default" fallback,
    e.g.:
        "customer_creation": {
            "default": "10/minute",
            "GET": "100/minute",
            "POST": "20/minute",
            "PUT": "30/minute",
            "PATCH": "30/minute",
            "DELETE": "10/300s",   # 10 requests per 5 minutes
        }
    A method not listed uses "default". A dict without "default" and
    without an entry for the current method disables throttling for that
    method (matches ScopedRateThrottle's own "no scope -> allow" rule).

Every limit is counted per PERSON, never shared across people. A logged-in
request is keyed by the user's pk. A request without a token (login, OTP,
forgot/reset password, token refresh, attendance kiosk, public grievance)
is keyed by whoever the request body/query names (username, email, emp_id,
phone, ...) — so N different people logging in from one office IP each get
their own 5/minute, instead of all N sharing one IP-wide 5/minute. Only a
request naming nobody falls back to the client IP.
"""

import hashlib

from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

# Request fields (body first, then query string) that identify the person
# behind an unauthenticated request, in priority order. Values are hashed
# into the cache key, so tokens/emails never sit in Redis key names.
PERSON_IDENT_FIELDS = (
    "username",
    "email",
    "emp_id",
    "staff_id_id",
    "phone",
    "wa_phone",
    "device_id",
    "session_token",
    "reset_token",
    "refresh",
)


def _request_value(request, field):
    for source in ("data", "query_params"):
        try:
            values = getattr(request, source)
            value = values.get(field) if hasattr(values, "get") else None
        except Exception:
            # Unparseable body: let the view report the parse error; the
            # throttle just falls back to the next source / the IP.
            continue
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def person_ident(throttle, request):
    """Stable per-person identity for a throttle cache key."""
    if request.user and request.user.is_authenticated:
        return f"user:{request.user.pk}"

    for field in PERSON_IDENT_FIELDS:
        value = _request_value(request, field)
        if value:
            digest = hashlib.sha256(value.encode()).hexdigest()[:32]
            return f"{field}:{digest}"

    return f"ip:{throttle.get_ident(request)}"


class PersonAnonRateThrottle(AnonRateThrottle):
    """AnonRateThrottle keyed per person (see person_ident) instead of per IP."""

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None  # UserRateThrottle covers logged-in requests.
        return self.cache_format % {
            "scope": self.scope,
            "ident": person_ident(self, request),
        }


class MethodScopedRateThrottle(ScopedRateThrottle):
    """Drop-in replacement for ScopedRateThrottle with per-method rates."""

    def allow_request(self, request, view):
        self.scope = getattr(view, self.scope_attr, None)
        if not self.scope:
            return True

        rate_config = self.get_rate()
        if isinstance(rate_config, dict):
            rate = rate_config.get(request.method) or rate_config.get("default")
        else:
            rate = rate_config

        if not rate:
            return True

        self.rate = rate
        self.num_requests, self.duration = self.parse_rate(self.rate)

        # SimpleRateThrottle.allow_request (not ScopedRateThrottle's, which
        # would re-derive self.rate via get_rate() and can't handle the
        # dict form above) does the actual Redis-backed counting/TTL.
        return super(ScopedRateThrottle, self).allow_request(request, view)

    def get_cache_key(self, request, view):
        # Method folded into the scope portion of the key so GET/POST/PUT/
        # PATCH/DELETE each get their own independent counter, and the
        # person (not the IP) as the ident, e.g.:
        #   throttle_customer_creation_GET_user:STF-0001
        #   throttle_platform_login_POST_username:<sha256 prefix>
        return self.cache_format % {
            "scope": f"{self.scope}_{request.method}",
            "ident": person_ident(self, request),
        }
