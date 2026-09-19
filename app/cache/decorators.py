"""
@cache_api — cache-aside decorator for a DRF viewset's read method
(list/retrieve/a custom @action). See app/cache/config.py to configure
enabled/ttl per scope, app/cache/keys.py for key shape, and
app/cache/invalidation.py for the write-side counterpart.

    class DepartmentViewSet(...):
        @cache_api("department_list")
        def list(self, request, *args, **kwargs):
            return super().list(request, *args, **kwargs)

Behavior:
  - No-op (bypasses Redis entirely) unless CACHE_CONFIG[scope]["enabled"]
    is True, and always a no-op for non-GET requests.
  - Cache key = scope + normalized query params [+ request.user.pk if
    vary_on_user, the default — several endpoints in this codebase return
    per-user-scoped data via StaffDataScope rather than a shared tenant
    id, so varying on user is the safe default; pass vary_on_user=False
    only once you've confirmed a view's response never depends on
    request.user].
  - Only successful (2xx) responses are cached; error/exception responses
    never are.
  - Stores serialized response.data (not the Response object or model
    instances), so it round-trips cleanly through Redis.
"""

from functools import wraps

from rest_framework.response import Response

from app.cache.config import get_cache_settings
from app.cache.invalidation import track_key
from app.cache.keys import build_cache_key
from app.cache.service import cache_get, cache_set


def cache_api(scope, vary_on_user=True):
    def decorator(view_method):
        @wraps(view_method)
        def wrapped(self, request, *args, **kwargs):
            settings_for_scope = get_cache_settings(scope)
            if request.method != "GET" or not settings_for_scope["enabled"]:
                return view_method(self, request, *args, **kwargs)

            user_id = None
            if vary_on_user and request.user and request.user.is_authenticated:
                user_id = getattr(request.user, "pk", None)

            key = build_cache_key(scope, params=request.query_params, user_id=user_id)

            cached = cache_get(key, scope=scope)
            if cached is not None:
                return Response(cached["data"], status=cached["status_code"])

            response = view_method(self, request, *args, **kwargs)
            if 200 <= response.status_code < 300:
                ttl = settings_for_scope["ttl"]
                cache_set(
                    key,
                    {"data": response.data, "status_code": response.status_code},
                    ttl,
                    scope=scope,
                )
                track_key(scope, key, ttl)
            return response

        return wrapped

    return decorator
