"""
Cache-aside read/write primitives against the dedicated app-cache Redis
alias (settings.CACHES["app_cache"] — separate from CACHES["default"],
which app.utils.throttling.MethodScopedRateThrottle uses for rate-limit
counters; see config/settings.py).

Redis is an optimization, never a dependency: every function here
swallows backend errors, logs them, and falls back to "no cache" so a
Redis outage degrades the API to normal MySQL-backed behavior instead of
breaking it.
"""

import logging

from django.core.cache import caches

logger = logging.getLogger("app.cache")

APP_CACHE_ALIAS = "app_cache"


def _cache():
    return caches[APP_CACHE_ALIAS]


def cache_get(key, scope):
    try:
        value = _cache().get(key)
    except Exception:
        logger.exception("CACHE ERROR: get failed for scope=%s", scope)
        return None

    if value is not None:
        logger.info("CACHE HIT: %s", scope)
    else:
        logger.info("CACHE MISS: %s", scope)
    return value


def cache_set(key, value, ttl, scope):
    try:
        _cache().set(key, value, timeout=ttl)
        logger.info("CACHE SET: %s TTL=%s", scope, ttl)
    except Exception:
        logger.exception("CACHE ERROR: set failed for scope=%s", scope)


def cache_delete_many(keys, scope):
    keys = [k for k in keys if k]
    if not keys:
        return
    try:
        _cache().delete_many(keys)
        logger.info("CACHE INVALIDATED: %s (%d keys)", scope, len(keys))
    except Exception:
        logger.exception("CACHE ERROR: invalidation failed for scope=%s", scope)


def cache_delete(key):
    try:
        _cache().delete(key)
    except Exception:
        logger.exception("CACHE ERROR: delete failed for key=%s", key)
