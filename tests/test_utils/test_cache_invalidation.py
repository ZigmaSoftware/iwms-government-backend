"""
Unit-level coverage for app/cache/invalidation.py's transaction.on_commit
behavior, independent of any viewset. Kept separate from
tests/superadmin_masters/test_api/test_state_cache.py's HTTP-level tests
because exercising POST/PUT/DELETE through StateViewSet currently fails
in this environment for an unrelated pre-existing reason:
AuditViewSetMixin always writes a StaffAudit row, and this test database
does not create that table (`no such table: staff_audit`).
"""
import pytest
from django.core.cache import caches
from django.db import transaction

from app.cache.invalidation import invalidate_on_commit, invalidate_scope, track_key
from app.cache.keys import build_cache_key


@pytest.fixture(autouse=True)
def _clear_app_cache():
    caches["app_cache"].clear()
    yield
    caches["app_cache"].clear()


@pytest.mark.django_db
def test_invalidate_scope_removes_every_tracked_key():
    key_a = build_cache_key("state_list", params={"status": "active"})
    key_b = build_cache_key("state_list", params={"status": "inactive"})

    caches["app_cache"].set(key_a, {"data": "a"}, 600)
    caches["app_cache"].set(key_b, {"data": "b"}, 600)
    track_key("state_list", key_a, 600)
    track_key("state_list", key_b, 600)

    invalidate_scope("state_list")

    assert caches["app_cache"].get(key_a) is None
    assert caches["app_cache"].get(key_b) is None


@pytest.mark.django_db
def test_invalidate_on_commit_fires_after_successful_commit(django_capture_on_commit_callbacks):
    key = build_cache_key("state_list", params={})
    caches["app_cache"].set(key, {"data": "cached"}, 600)
    track_key("state_list", key, 600)

    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            invalidate_on_commit("state_list")

    assert caches["app_cache"].get(key) is None


@pytest.mark.django_db
def test_invalidate_on_commit_does_not_fire_on_rollback(django_capture_on_commit_callbacks):
    key = build_cache_key("state_list", params={})
    caches["app_cache"].set(key, {"data": "cached"}, 600)
    track_key("state_list", key, 600)

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        try:
            with transaction.atomic():
                invalidate_on_commit("state_list")
                raise ValueError("simulated failure forcing rollback")
        except ValueError:
            pass

    # transaction.on_commit callbacks registered inside a rolled-back
    # atomic block are discarded by Django itself, never executed.
    assert callbacks == []
    assert caches["app_cache"].get(key) == {"data": "cached"}


@pytest.mark.django_db
def test_invalidate_scope_is_safe_when_nothing_was_ever_cached():
    invalidate_scope("a_scope_with_nothing_cached")  # must not raise
