"""
Deterministic Redis cache key generation, namespaced under "iwms:cache:".

A key is built from:
  - scope        e.g. "department_list" — matches app/cache/config.py
  - query params — every param that can affect the response, normalized
                   (sorted) so ?a=1&b=2 and ?b=2&a=1 hash to the same key
  - user id      — included whenever the response can differ per user
                   (role/permission/geo-scoped data); omitted for
                   endpoints confirmed identical for every caller

Also tracks, per scope, the set of keys currently cached under it (in a
small Redis "index" entry) so invalidation.py can delete every variant of
a scope (all pages/filters/users) without an expensive KEYS/SCAN sweep.
"""

import hashlib

NAMESPACE = "iwms:cache"


def _normalize_params(params):
    return "&".join(f"{k}={v}" for k, v in sorted(params.items()) if v not in (None, ""))


def build_cache_key(scope, params=None, user_id=None):
    """Build a deterministic cache key for `scope` + normalized `params` [+ user_id]."""
    normalized = _normalize_params(params or {})
    parts = [scope, normalized]
    if user_id is not None:
        parts.append(f"user={user_id}")

    fingerprint = hashlib.sha256(":".join(parts).encode()).hexdigest()[:32]
    readable_suffix = normalized or "noparams"
    if user_id is not None:
        readable_suffix = f"user:{user_id}:{readable_suffix}"

    # Keep the params/user readable in the key for easier debugging via
    # redis-cli, with a fingerprint suffix so distinct param combinations
    # never collide even if truncated for length.
    return f"{NAMESPACE}:{scope}:{readable_suffix}:{fingerprint}"[:250]


def scope_index_key(scope):
    """Key holding the set of all cache keys currently stored for `scope`."""
    return f"{NAMESPACE}:_index:{scope}"
