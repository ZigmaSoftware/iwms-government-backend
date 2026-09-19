"""
Cache-aside behavior for the State master list & detail endpoints
(app/cache/) — the pilot API for Redis response caching, exercised
end-to-end via the real HTTP API. Once this holds up, the same pattern
(see app/viewsets/superadmin/common_masters/state_viewset.py) can be
extended to other master/reference/dashboard endpoints.

Rate limiting is disabled and both cache aliases use per-test LocMemCache
in config/test_settings.py, so these tests don't depend on a live Redis
instance or trip the "state" throttle scope.

Write (POST/PUT/DELETE) invalidation is covered at the unit level in
tests/test_utils/test_cache_invalidation.py instead of through this
viewset, because AuditViewSetMixin.perform_create/perform_update
unconditionally writes a StaffAudit row, and this environment's test
database does not create that table (`no such table: staff_audit`) — a
pre-existing gap unrelated to caching.
"""
import jwt
import pytest
from django.conf import settings
from django.core.cache import caches
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from app.cache.config import CACHE_CONFIG, get_cache_settings
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.superadmin_masters.auth_user import User

STATES_URL = "/api/v1/common-masters/states/"


@pytest.fixture(autouse=True)
def _clear_app_cache():
    caches["app_cache"].clear()
    yield
    caches["app_cache"].clear()


@pytest.fixture
def api_client(db):
    # app.authentication.jwt.JWTUserAuthentication only recognizes a
    # request.user already set by something else if it has
    # staff_unique_id/customer_name — a plain app.User (platform admin)
    # doesn't, so DRF's force_authenticate is a no-op for this model here.
    # Mint a real token instead, matching the fallback branch that
    # resolves platform admins by unique_id.
    #
    # is_superuser=True also short-circuits both
    # ModulePermissionMiddleware's resource-permission check and
    # filter_flat_geo_queryset_by_requester_scope's geo filtering
    # (app/utils/hierarchy.py:_unscoped_result returns the queryset
    # unfiltered for a superuser) — without it a fresh User has no
    # StaffDataScope and would see zero states.
    user = User.objects.create_user(username="cache-tester", is_superuser=True)
    token = jwt.encode({"unique_id": user.unique_id}, settings.SECRET_KEY, algorithm="HS256")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def continent(db):
    return Continent.objects.create(name="Asia")


@pytest.fixture
def country(continent):
    return Country.objects.create(continent_id=continent, name="India")


def _names(response):
    body = response.json()
    rows = body["results"] if isinstance(body, dict) and "results" in body else body
    return {row["state_name"] for row in rows}


@pytest.mark.django_db
def test_list_cache_miss_then_hit(api_client, country, continent):
    State.objects.create(country_id=country, continent_id=continent, name="Tamil Nadu")

    first = api_client.get(STATES_URL)
    assert first.status_code == 200, first.content

    # A cache hit must skip the State query entirely — auth/permission
    # middleware still runs its own (unrelated) queries on every request,
    # so this asserts on the State table specifically.
    with CaptureQueriesContext(connection) as ctx:
        second = api_client.get(STATES_URL)

    # Match the State table specifically ("app_state", quoted) — a plain
    # substring check also matches unrelated tables like
    # app_stateleaderlogin (queried by auth/permission middleware on
    # every request, cache hit or not).
    # Match only a query whose primary FROM target is app_state (the
    # viewset's own list query) — not incidental joins against app_state,
    # e.g. JWTUserAuthentication's per-request
    # "FROM app_stateleaderlogin INNER JOIN app_state" lookup while
    # resolving request.user, which runs on every request regardless of
    # caching.
    state_queries = [q for q in ctx.captured_queries if 'from "app_state"' in q["sql"].lower()]
    assert state_queries == []
    assert second.status_code == 200
    assert second.json() == first.json()


@pytest.mark.django_db
def test_different_query_params_get_independent_cache_entries(api_client, continent):
    india = Country.objects.create(continent_id=continent, name="India")
    lanka = Country.objects.create(continent_id=continent, name="Sri Lanka")
    State.objects.create(country_id=india, continent_id=continent, name="Tamil Nadu")
    State.objects.create(country_id=lanka, continent_id=continent, name="Western Province")

    india_states = api_client.get(STATES_URL, {"country": india.unique_id})
    lanka_states = api_client.get(STATES_URL, {"country": lanka.unique_id})

    assert _names(india_states) == {"Tamil Nadu"}
    assert _names(lanka_states) == {"Western Province"}


@pytest.mark.django_db
def test_param_order_does_not_change_cache_key(api_client, country, continent):
    State.objects.create(country_id=country, continent_id=continent, name="Tamil Nadu")

    r1 = api_client.get(STATES_URL + f"?country={country.unique_id}&continent=")
    r2 = api_client.get(STATES_URL + f"?continent=&country={country.unique_id}")

    assert r1.json() == r2.json()


@pytest.mark.django_db
def test_new_state_not_visible_until_cache_expires_or_is_invalidated(api_client, country, continent):
    """Documents cache-aside's inherent staleness window: writing directly
    to the DB (bypassing the viewset, so no invalidation fires) must not be
    reflected until the TTL passes — proves the GET path is actually
    reading from cache, not always hitting MySQL."""
    State.objects.create(country_id=country, continent_id=continent, name="Tamil Nadu")
    first = api_client.get(STATES_URL)
    assert _names(first) == {"Tamil Nadu"}

    State.objects.create(country_id=country, continent_id=continent, name="Kerala")

    second = api_client.get(STATES_URL)
    assert _names(second) == {"Tamil Nadu"}  # still cached — new row not yet visible


@pytest.mark.django_db
def test_redis_failure_falls_back_to_database(api_client, country, continent, monkeypatch):
    """If the cache backend raises (e.g. Redis is down), the API must
    still return the correct data from MySQL instead of erroring out."""
    State.objects.create(country_id=country, continent_id=continent, name="Tamil Nadu")

    from app.cache import service

    def _boom(*args, **kwargs):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(service, "_cache", _boom)

    resp = api_client.get(STATES_URL)
    assert resp.status_code == 200
    assert _names(resp) == {"Tamil Nadu"}


def test_disabled_scope_config_defaults_safely():
    assert get_cache_settings("not_a_real_scope") == {"enabled": False, "ttl": 0}
    assert CACHE_CONFIG["state_list"]["enabled"] is True
