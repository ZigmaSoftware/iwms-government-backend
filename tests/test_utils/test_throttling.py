"""
Unit-level coverage for app/utils/throttling.py: every rate limit is
counted per person, never shared across people. The throttle classes are
exercised directly because config/test_settings.py disables throttling
for HTTP-level tests.
"""
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import caches
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from app.utils.throttling import MethodScopedRateThrottle, PersonAnonRateThrottle

LIMIT = "5/minute"
OFFICE_IP = "10.0.0.5"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    caches["default"].clear()
    yield
    caches["default"].clear()


@pytest.fixture
def scoped_rates(monkeypatch):
    monkeypatch.setattr(
        MethodScopedRateThrottle, "THROTTLE_RATES", {"platform_login": LIMIT, "ward": LIMIT}
    )
    monkeypatch.setattr(PersonAnonRateThrottle, "THROTTLE_RATES", {"anon": LIMIT})


def _anon_request(data=None, ip=OFFICE_IP):
    raw = APIRequestFactory().post("/login/", data or {}, format="json", REMOTE_ADDR=ip)
    request = Request(raw, parsers=[JSONParser()])
    request.user = AnonymousUser()
    return request


def _user_request(pk, ip=OFFICE_IP):
    raw = APIRequestFactory().get("/wards/", REMOTE_ADDR=ip)
    request = Request(raw)
    request.user = SimpleNamespace(pk=pk, is_authenticated=True)
    return request


def _hits(throttle_cls, scope, request_factory, count):
    view = SimpleNamespace(throttle_scope=scope)
    return [throttle_cls().allow_request(request_factory(), view) for _ in range(count)]


@pytest.mark.parametrize("throttle_cls, scope", [
    (MethodScopedRateThrottle, "platform_login"),
    (PersonAnonRateThrottle, None),
])
def test_login_limit_is_per_username_not_per_shared_ip(scoped_rates, throttle_cls, scope):
    # Ten people log in 3 times each from the same office IP: 30 requests
    # from one IP, but nobody exceeds their own 5/minute.
    for n in range(10):
        hits = _hits(throttle_cls, scope, lambda: _anon_request({"username": f"staff{n}"}), 3)
        assert all(hits)


def test_one_username_is_blocked_after_its_own_limit(scoped_rates):
    hits = _hits(MethodScopedRateThrottle, "platform_login",
                 lambda: _anon_request({"username": "staff1"}), 6)
    assert hits == [True] * 5 + [False]

    # A different person from the same IP is unaffected.
    assert _hits(MethodScopedRateThrottle, "platform_login",
                 lambda: _anon_request({"username": "staff2"}), 1) == [True]


def test_username_is_case_insensitive(scoped_rates):
    names = iter(["Staff1", "STAFF1", "staff1", " staff1 ", "sTaFf1", "staff1"])
    hits = _hits(MethodScopedRateThrottle, "platform_login",
                 lambda: _anon_request({"username": next(names)}), 6)
    assert hits[-1] is False


def test_authenticated_users_have_independent_counters(scoped_rates):
    assert all(_hits(MethodScopedRateThrottle, "ward", lambda: _user_request("STF-0001"), 3))
    assert all(_hits(MethodScopedRateThrottle, "ward", lambda: _user_request("CUS-0001"), 3))


def test_request_naming_nobody_falls_back_to_ip(scoped_rates):
    hits = _hits(MethodScopedRateThrottle, "platform_login", lambda: _anon_request(), 6)
    assert hits == [True] * 5 + [False]
    assert _hits(MethodScopedRateThrottle, "platform_login",
                 lambda: _anon_request(ip="10.0.0.6"), 1) == [True]
