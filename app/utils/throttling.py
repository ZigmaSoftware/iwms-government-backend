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
"""

from rest_framework.throttling import ScopedRateThrottle


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
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        # Method folded into the scope portion of the key so GET/POST/PUT/
        # PATCH/DELETE each get their own independent counter, e.g.:
        #   throttle_customer_creation_GET_10.0.0.5
        #   throttle_customer_creation_POST_10.0.0.5
        return self.cache_format % {
            "scope": f"{self.scope}_{request.method}",
            "ident": ident,
        }
