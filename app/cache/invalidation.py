"""
Cache invalidation: track every key stored for a scope, then blow away
the whole scope in one call after a successful MySQL write.

Keys are tracked (not pattern-matched) because django-redis's KEYS/SCAN
is a full-database sweep with no per-app isolation guarantee — tracking
the exact set of keys a scope has ever produced is O(1) to invalidate
and doesn't depend on Redis pattern support.

Callers must invalidate from inside transaction.on_commit(...) so a
rolled-back write never invalidates a still-valid cache (see
invalidate_on_commit below, and its usage in viewset perform_create/
perform_update/perform_destroy hooks).
"""

from django.db import transaction

from app.cache.keys import scope_index_key
from app.cache.service import cache_delete_many, cache_get, cache_set

_INDEX_TTL = 24 * 60 * 60  # keys outlive any realistic per-API TTL


def track_key(scope, key, ttl):
    """Record `key` as belonging to `scope`, so invalidate_scope can find it.

    Read-modify-write, not atomic: two cache-misses for the same scope
    racing concurrently can each read the index before the other's write
    lands, and one update is lost. Acceptable here — a lost index entry
    only means that one extra key outlives an invalidation and expires
    on its own TTL instead, it never serves data past that TTL. Do not
    rely on this index for correctness-critical invalidation of
    high-write-concurrency scopes without adding real locking first.
    """
    index_key = scope_index_key(scope)
    keys = cache_get(index_key, scope=f"{scope}:_index") or set()
    keys.add(key)
    cache_set(index_key, keys, max(ttl, _INDEX_TTL), scope=f"{scope}:_index")


def invalidate_scope(*scopes):
    """Delete every cached response tracked under each of the given scopes."""
    for scope in scopes:
        index_key = scope_index_key(scope)
        keys = cache_get(index_key, scope=f"{scope}:_index") or set()
        cache_delete_many(keys, scope=scope)
        cache_delete_many([index_key], scope=f"{scope}:_index")


def invalidate_on_commit(*scopes):
    """Schedule invalidate_scope(*scopes) to run only after the current DB
    transaction commits successfully. A rollback never triggers it.

    Usage:
        with transaction.atomic():
            department.save()
            invalidate_on_commit("department_list", "department_detail")
    """
    transaction.on_commit(lambda: invalidate_scope(*scopes))
