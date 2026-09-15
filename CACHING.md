# Redis Response Caching — File-by-File Report

Cache-aside response caching, currently piloted on a single API (the
State master) before being extended anywhere else. Built alongside the
existing rate-limiting system (`app/utils/throttling.py` +
`config/throttle_rates.py`) but kept fully independent — separate files,
separate Redis database, separate on/off switches.

```
MySQL = source of truth
Redis = disposable cache (db 1, separate from throttling's db 0)
TTL   = safety net (data heals itself even with zero invalidation)
Invalidation = freshness mechanism, fired only after a committed write
```

No Celery, no Nginx — everything runs inside the existing Django request
cycle.

## Where every piece lives

```
config/settings.py                                        # Redis connections + logging
app/cache/
├── __init__.py                                            # empty, makes it a package
├── config.py                                               # per-API on/off + TTL
├── keys.py                                                 # deterministic Redis key builder
├── service.py                                              # the only file that talks to Redis
├── decorators.py                                           # @cache_api — the read-side wrapper
└── invalidation.py                                         # the write-side counterpart
app/viewsets/superadmin/common_masters/state_viewset.py     # the one API currently wired up
tests/superadmin_masters/test_api/test_state_cache.py       # HTTP-level tests
tests/test_utils/test_cache_invalidation.py                 # unit-level invalidation tests
```

Nine files touch caching in total. Below is what each one does and why
it exists as a separate file rather than being folded into another.

---

## 1. `config/settings.py` — Redis connections + log visibility

Two independent `django-redis` cache aliases:

```python
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
REDIS_CACHE_URL = os.getenv("REDIS_CACHE_URL", "redis://127.0.0.1:6379/1")

CACHES = {
    "default": {...LOCATION: REDIS_URL...},        # db 0 — throttling counters only
    "app_cache": {...LOCATION: REDIS_CACHE_URL...}, # db 1 — this response cache only
}
```

**Why two aliases instead of one:** `CACHES["default"]` already existed
for `app.utils.throttling.MethodScopedRateThrottle`'s rate-limit
counters. Reusing it for response caching would mean flushing the cache
during an incident also resets everyone's rate limits, and vice versa —
two unrelated concerns sharing one blast radius. `app_cache` on db 1
can be flushed, monitored, or migrated independently.

Also defines `LOGGING`, scoped to just the `app.cache` logger at `INFO`,
printed to console:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"app.cache": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
```

**Why this was needed:** the project had no `LOGGING` config at all, so
Django's implicit default only surfaces `WARNING`+ — every `CACHE
HIT`/`MISS`/`SET` log call in `service.py` would otherwise be silently
dropped and nothing would ever appear on the console.

---

## 2. `app/cache/config.py` — the on/off + TTL switchboard

```python
CACHE_CONFIG = {
    "state_list": {"enabled": True, "ttl": 600},    # 10 min
    "state_detail": {"enabled": True, "ttl": 300},   # 5 min
}

def get_cache_settings(scope):
    return CACHE_CONFIG.get(scope, {"enabled": False, "ttl": 0})
```

**Purpose:** the single place that decides, per API, whether caching is
on and for how long. A "scope" is just a short string a view opts into
(`"state_list"`, `"state_detail"`). Anything not listed here defaults to
`{"enabled": False}` — caching is opt-in, never automatic.

**Why it's a separate file from `decorators.py`:** so a developer
changing a TTL or flipping caching off for one API only ever needs to
edit this one file — no risk of touching the mechanism itself.
Deliberately not merged with `config/throttle_rates.py` either: caching
and rate limiting are unrelated knobs on unrelated systems, even though
both happen to be "a dict of settings per API scope."

**Currently enabled:** only `state_list` and `state_detail`. Nothing
else in the codebase is cached yet.

---

## 3. `app/cache/keys.py` — deterministic Redis key generation

```python
NAMESPACE = "iwms:cache"

def build_cache_key(scope, params=None, user_id=None):
    # sorts + normalizes query params, optionally appends user_id,
    # hashes everything, returns e.g.:
    # iwms:cache:state_list:user:7:country=IND-001:<sha256-fingerprint>

def scope_index_key(scope):
    # iwms:cache:_index:state_list
```

**Purpose:** guarantees that the same logical request always produces
the same cache key, and that different requests never collide.

- Query params are sorted before hashing, so `?a=1&b=2` and `?b=2&a=1`
  produce an identical key.
- Empty params (`?corporation_id=`) are stripped during normalization.
- A `user=<pk>` segment is appended whenever the caller says the
  response varies per user (see `decorators.py`'s `vary_on_user` below).
- The human-readable scope/params/user prefix is kept in the key (for
  quick `redis-cli` inspection), with a SHA-256 fingerprint suffix so
  truncation or unusual characters in params can never cause a collision.

`scope_index_key` builds the name of a second, bookkeeping key per scope
— a small Redis set listing every cache key that scope has ever
produced. `invalidation.py` reads this to know what to delete.

**Why it's separate from `service.py`:** key *shape* (what string to use)
and key *storage* (how to read/write to Redis) are different concerns —
this file has zero Redis I/O in it, purely string logic, which makes it
trivially unit-testable without mocking Redis at all.

---

## 4. `app/cache/service.py` — the only file that touches Redis

```python
APP_CACHE_ALIAS = "app_cache"

def cache_get(key, scope): ...   # try/except around caches["app_cache"].get()
def cache_set(key, value, ttl, scope): ...
def cache_delete_many(keys, scope): ...
def cache_delete(key): ...
```

**Purpose:** every read/write against the `app_cache` Redis alias goes
through exactly these four functions. Nothing else in the codebase calls
`caches["app_cache"]` directly.

**Why this matters — the error-safety guarantee:** each function wraps
its Redis call in `try/except Exception`, logs via `logger.exception(...)`,
and returns `None`/no-ops on failure instead of raising. This is what
makes Redis an *optimization* rather than a *dependency* — if Redis is
down, `cache_get` returns `None` (behaves exactly like a cache miss),
`cache_set`/`cache_delete_many` silently fail to persist, and the API
falls through to MySQL and still returns a correct 200. No cached
endpoint can turn a Redis outage into a 500.

**Why this is a separate file from `decorators.py`/`invalidation.py`:**
centralizing all Redis I/O in one narrow file means the error-handling
and logging behavior only needs to be written once and reviewed once —
every other file just calls these functions and inherits that safety
for free.

**Logging emitted here** (this is the entire source of the `CACHE
HIT`/`MISS`/`SET`/`INVALIDATED`/`ERROR` lines you see in the console):
```
CACHE HIT: state_list
CACHE MISS: state_list
CACHE SET: state_list TTL=600
CACHE INVALIDATED: state_list (3 keys)
CACHE ERROR: get failed for scope=state_list   (with full traceback)
```
No response payloads or user-identifying data are ever logged — only
scope names and counts.

---

## 5. `app/cache/decorators.py` — `@cache_api`, the read-side wrapper

```python
def cache_api(scope, vary_on_user=True):
    def decorator(view_method):
        def wrapped(self, request, *args, **kwargs):
            settings_for_scope = get_cache_settings(scope)      # from config.py
            if request.method != "GET" or not settings_for_scope["enabled"]:
                return view_method(self, request, *args, **kwargs)   # bypass entirely

            user_id = request.user.pk if vary_on_user and request.user.is_authenticated else None
            key = build_cache_key(scope, params=request.query_params, user_id=user_id)  # from keys.py

            cached = cache_get(key, scope=scope)                # from service.py
            if cached is not None:
                return Response(cached["data"], status=cached["status_code"])

            response = view_method(self, request, *args, **kwargs)   # cache miss → run the real view
            if 200 <= response.status_code < 300:
                cache_set(key, {"data": response.data, "status_code": response.status_code},
                          settings_for_scope["ttl"], scope=scope)     # from service.py
                track_key(scope, key, settings_for_scope["ttl"])      # from invalidation.py
            return response
        return wrapped
    return decorator
```

**Purpose:** this is the actual cache-aside pattern, wired onto a
viewset method with one line:

```python
@cache_api("state_list")
def list(self, request, *args, **kwargs):
    return super().list(request, *args, **kwargs)
```

**Step by step for a `GET`:**
1. If the scope is disabled in `config.py`, or the request isn't `GET`
   → skip everything, call the real view, done.
2. Build the key (`keys.py`).
3. Ask Redis for it (`service.py`).
4. **Hit** → return the cached `data`/`status_code` as a fresh `Response`
   object — no DB query, no serializer work.
5. **Miss** → run the real view, and if it succeeded (2xx), store the
   result and register the key with `invalidation.py`'s `track_key` so a
   future write knows this key exists and can delete it.

**`vary_on_user` (default `True`):** whether `request.user.pk` is folded
into the key. `StateViewSet` keeps the default because its
`get_queryset()` filters by the requester's own geo scope
(`filter_flat_geo_queryset_by_requester_scope`) — two different users can
legitimately see different State lists, so their cached responses must
never be shared. Set `vary_on_user=False` only for an API confirmed to
return identical data to every caller regardless of who's asking.

**Why it only ever caches 2xx:** error/exception responses, validation
failures, and permission denials are never cached — a transient 500 or a
403 for one user must never be replayed to the next request.

**Why it's a separate file from `service.py`:** this file knows *when* to
cache (the policy — HTTP method, status code, config lookup);
`service.py` only knows *how* to talk to Redis safely. Keeping policy and
mechanism apart means the mechanism can be reused unchanged if the policy
ever needs to get more complex (e.g. stampede protection, per-role
variation) without touching Redis-handling code at all.

---

## 6. `app/cache/invalidation.py` — the write-side counterpart

```python
_INDEX_TTL = 24 * 60 * 60

def track_key(scope, key, ttl):
    # reads the scope's index set, adds `key`, writes it back
    # (read-modify-write — see the race-condition note in the file itself)

def invalidate_scope(*scopes):
    # for each scope: read its index set, delete every key in it,
    # then delete the index itself

def invalidate_on_commit(*scopes):
    transaction.on_commit(lambda: invalidate_scope(*scopes))
```

**Purpose:** three functions covering the full lifecycle of "forget
what's cached for this scope."

- **`track_key`** is called from `decorators.py` every time a fresh
  response is cached — it's how the system remembers *which* keys exist
  for a scope (pagination pages, different filters, different users all
  produce different keys, and all of them need to be found later).
- **`invalidate_scope`** is the actual eviction: delete every key the
  index remembers, then delete the index itself. This is what a viewset
  calls after a write.
- **`invalidate_on_commit`** wraps `invalidate_scope` in Django's
  `transaction.on_commit(...)`. This is the single most important
  correctness guarantee in the whole system: if the surrounding
  transaction rolls back (e.g. a validation error deep in `save()`),
  Django itself discards the `on_commit` callback — `invalidate_scope`
  never runs. A failed write can never incorrectly evict a cache entry
  for data that never actually changed.

**Why keys are *tracked* instead of pattern-deleted:** Redis's
`KEYS`/`SCAN` is a full-database sweep with no per-app isolation — using
it here would mean either scanning the entire `app_cache` DB on every
invalidation, or trusting a naming convention to scope it safely. Keeping
an explicit per-scope index is O(1) to invalidate and works on any cache
backend, not just ones that support key patterns.

**Known tradeoff, documented in the file:** `track_key` is a
read-modify-write, not atomic. Two concurrent cache-misses for the same
scope can race and one index update can be lost. This is deliberately
accepted for a low-write-concurrency API like State — the only
consequence is one extra key outliving an invalidation and expiring on
its own TTL instead, never serving stale data past that TTL.

**Why it's a separate file from `decorators.py`:** invalidation is
called from a completely different place in the request lifecycle
(`perform_create`/`update`/`destroy`, not `list`/`retrieve`), and needs
its own transaction-safety story (`transaction.on_commit`) that reading
doesn't need at all.

---

## 7. `app/viewsets/superadmin/common_masters/state_viewset.py` — the one API wired up

```python
STATE_CACHE_SCOPES = ("state_list", "state_detail")

class StateViewSet(LiteListMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    ...
    @cache_api("state_list")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @cache_api("state_detail")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        invalidate_on_commit(*STATE_CACHE_SCOPES)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        invalidate_on_commit(*STATE_CACHE_SCOPES)

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_on_commit(*STATE_CACHE_SCOPES)
```

**Purpose:** the only file in the entire codebase, besides tests, that
actually *uses* the cache package right now. Everything above is
infrastructure; this is the pilot consumer.

**Why State was picked as the pilot** (not Department/Designation, which
were tried and then deliberately rolled back): State is a low-traffic,
well-understood master-data endpoint, but its `get_queryset()` already
filters by the requester's geo scope — making it a genuine test of the
`vary_on_user=True` code path, not just the simpler "same for everyone"
case. Proving the harder case first means extending to simpler APIs
later is strictly easier.

---

## 8 & 9. Tests

**`tests/superadmin_masters/test_api/test_state_cache.py`** — HTTP-level,
hits the real `/api/v1/common-masters/states/` endpoint:
- cache hit skips the `State` table query entirely (confirmed by
  inspecting captured SQL, filtering out unrelated auth-middleware
  queries that incidentally join `app_state`)
- distinct query params (`?country=...`) get distinct cache entries
- param order doesn't change the cache key
- writing directly to the DB (bypassing the viewset) shows the staleness
  window — proves reads are actually coming from cache, not always MySQL
- Redis raising an exception still returns a correct 200 from MySQL

**`tests/test_utils/test_cache_invalidation.py`** — unit-level, calls
`invalidation.py` directly:
- `invalidate_scope` clears every tracked key
- `invalidate_on_commit` fires only after a real commit
  (`django_capture_on_commit_callbacks`)
- `invalidate_on_commit` is discarded on rollback and never fires

**Why POST/PUT/DELETE invalidation is tested at the unit level instead of
through the live HTTP viewset:** `AuditViewSetMixin` (used by every
ModelViewSet in this project, including `StateViewSet`) unconditionally
writes a `StaffAudit` row on every create/update/destroy, and this
environment's test database does not create that table
(`no such table: staff_audit`) — a pre-existing gap unrelated to caching,
confirmed to fail identically before any of these changes.

Run just these:
```bash
python -m pytest tests/superadmin_masters/test_api/test_state_cache.py tests/test_utils/test_cache_invalidation.py -q
```

---

## How to check it live

- **Console logs** (needs the `LOGGING` config above): hit the state list
  endpoint twice — first request logs `MISS` then `SET`, second logs
  `HIT`.
- **Redis directly:**
  ```bash
  redis-cli -n 1 KEYS 'iwms:cache:state_*'
  redis-cli -n 1 SMEMBERS iwms:cache:_index:state_list
  redis-cli -n 1 TTL <a key from above>
  redis-cli -n 1 GET <a key from above>
  ```
- **Manual full flush** (safe — isolated to db 1, throttling on db 0
  untouched):
  ```bash
  redis-cli -n 1 FLUSHDB
  ```
- **From a Django shell:**
  ```python
  from app.cache.invalidation import invalidate_scope
  invalidate_scope("state_list", "state_detail")
  ```

## What's intentionally not cached (yet)

- Every other API in the codebase — Department, Designation, dashboards,
  etc. `CACHE_CONFIG` only lists `state_list`/`state_detail` right now.
- `POST`/`PUT`/`PATCH`/`DELETE` responses — `@cache_api` is a no-op for
  any non-`GET` method, always.
- Cache-stampede protection (a lock around a popular key's regeneration)
  — not needed at State's traffic level; revisit before enabling a
  high-traffic scope like a dashboard summary.

## How to extend this to a new API

1. Add a scope + TTL to `app/cache/config.py`.
2. Decorate `list`/`retrieve` with `@cache_api("your_scope")` in the
   target viewset (set `vary_on_user=False` only once you've confirmed
   the queryset never depends on `request.user`).
3. Call `invalidate_on_commit("your_scope", ...)` from
   `perform_create`/`perform_update`/`perform_destroy`.
4. If another serializer embeds data from this model, add its scopes to
   the invalidation call too (cross-resource invalidation).
