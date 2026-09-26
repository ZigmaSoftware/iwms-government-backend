"""Request-scoped cache for plain unique_id reference lookups.

Models no longer carry ForeignKeys, so resolving e.g. `plan.vehicle` is a
query per access. Inside a request, `get()` remembers every row it resolves
(including misses), so a list page that references the same staff / vehicle /
template on many rows queries each one once. `prime()` loads many ids in one
query up front.

The cache only exists while `RefCacheMiddleware` has a scope open; outside a
request (seeders, management commands, the scheduler thread) every call goes
straight to the database, so nothing can go stale across requests. Saving or
deleting a row evicts it from the current scope.
"""

import contextvars

from django.db.models.signals import post_delete, post_save

_scope = contextvars.ContextVar("plain_ref_cache", default=None)


def _field_name(model, field):
    return field or model._meta.pk.name


def get(model, value, field=None):
    """Return the `model` row whose `field` (default: pk) equals `value`,
    or None. Cached for the rest of the current request."""
    if value in (None, ""):
        return None
    field = _field_name(model, field)
    store = _scope.get()
    if store is None:
        return model._default_manager.filter(**{field: value}).first()
    key = (model._meta.label_lower, field, value)
    if key not in store:
        store[key] = model._default_manager.filter(**{field: value}).first()
    return store[key]


def prime(model, values, field=None):
    """Load every `model` row whose `field` is in `values` with one query
    into the current request's cache. No-op outside a request."""
    store = _scope.get()
    if store is None:
        return
    field = _field_name(model, field)
    label = model._meta.label_lower
    missing = {v for v in values if v not in (None, "") and (label, field, v) not in store}
    if not missing:
        return
    found = {
        getattr(row, field): row
        for row in model._default_manager.filter(**{f"{field}__in": missing})
    }
    for value in missing:
        store[(label, field, value)] = found.get(value)


def _evict(sender, instance, **kwargs):
    store = _scope.get()
    if not store:
        return
    label = sender._meta.label_lower
    for key in [k for k in store if k[0] == label]:
        del store[key]


post_save.connect(_evict, dispatch_uid="ref_cache_evict_save")
post_delete.connect(_evict, dispatch_uid="ref_cache_evict_delete")


class RefCacheMiddleware:
    """Opens a fresh reference cache for each request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _scope.set({})
        try:
            return self.get_response(request)
        finally:
            _scope.reset(token)
