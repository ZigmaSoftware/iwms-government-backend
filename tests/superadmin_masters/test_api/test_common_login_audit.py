"""Transaction (common) audit and login audit trails: actor capture, geo
stamping, requester hierarchy scoping, filters and the filter-options action.

Scoping is exercised through the viewsets directly (APIRequestFactory +
force_authenticate) so a scoped staff user isn't first refused by the module
permission middleware — that gate is covered elsewhere; this file is about
which rows a requester who IS allowed in gets to see.
"""
import jwt
import pytest
from django.conf import settings
from django.core.cache import caches
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.superadmin.audits.login_audit import LoginAudit
from app.models.superadmin.staff_management.staff_data_scope import StaffDataScope
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.auth_user import User
from app.utils.audit_mixin import _write_audit
from app.utils.common_audit import CommonAudit
from app.viewsets.superadmin.audits.common_audit_viewset import CommonAuditViewSet
from app.viewsets.superadmin.audits.login_audit_viewset import LoginAuditViewSet

COMMON_URL = "/api/v1/audits/common-audit/"
LOGIN_URL = "/api/v1/audits/login-audit/"


@pytest.fixture(autouse=True)
def _clear_app_cache():
    caches["app_cache"].clear()
    yield
    caches["app_cache"].clear()


@pytest.fixture
def superuser(db):
    return User.objects.create_user(username="audit-root", is_superuser=True)


@pytest.fixture
def api_client(superuser):
    token = jwt.encode({"unique_id": superuser.unique_id}, settings.SECRET_KEY, algorithm="HS256")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def geo(db):
    district_a = District.objects.create(
        unique_id="DIST-A", name="Alpha District", state_id="ST-1",
        country_id="CTRY-1", continent_id="CONT-1",
    )
    district_b = District.objects.create(
        unique_id="DIST-B", name="Beta District", state_id="ST-1",
        country_id="CTRY-1", continent_id="CONT-1",
    )
    corp_a = Corporation.objects.create(
        unique_id="CORP-A", corporation_name="Alpha Corporation",
        state_id="ST-1", district_id="DIST-A", area_type_id="AT-U",
    )
    corp_b = Corporation.objects.create(
        unique_id="CORP-B", corporation_name="Beta Corporation",
        state_id="ST-1", district_id="DIST-B", area_type_id="AT-U",
    )
    return {"district_a": district_a, "district_b": district_b, "corp_a": corp_a, "corp_b": corp_b}


def _staff(username, district, corporation, **extra):
    return Staffcreation.objects.create(
        username=username,
        employee_name=f"{username.title()} Person",
        login_enabled=True,
        state_id="ST-1",
        district_id=district,
        area_type_id="AT-U",
        corporation_id=corporation,
        **extra,
    )


def _audit(**fields):
    defaults = {"module_name": "masters", "endpoint_name": "ward", "method": "POST"}
    defaults.update(fields)
    return CommonAudit.objects.create(**defaults)


def _scoped(staff, **scope):
    StaffDataScope.objects.create(staff_id=staff.staff_unique_id, **scope)
    return staff


def _get(client, url, params):
    # Unpaginated when no ?limit/?page is sent (LimitOffsetWithPage).
    response = client.get(url, params)
    assert response.status_code == 200, response.content
    return response.json()


def _list(viewset, user, params=None, action="list", path="/"):
    request = APIRequestFactory().get(path, params or {})
    force_authenticate(request, user=user)
    response = viewset.as_view({"get": action})(request)
    assert response.status_code == 200, response.data
    data = response.data
    return data["results"] if isinstance(data, dict) and "results" in data else data


@pytest.mark.django_db
class TestCommonAuditWrites:
    def test_write_audit_persists_actor_and_geo(self, geo):
        actor = _staff("writer", "DIST-A", "CORP-A")
        record = _staff("target", "DIST-B", "CORP-B")

        row = _write_audit(
            module_name="staff", endpoint_name="staffcreation", method="PATCH",
            instance=record, previous_data=None, new_data={}, created_by=str(actor),
            actor=actor,
        )
        row.refresh_from_db()

        assert row.created_by_id == actor.staff_unique_id
        assert row.created_by_name == "Writer Person"
        assert row.created_by_type == "staff"
        # Filed under the changed record's geo, not the actor's.
        assert (row.district, row.corporation) == ("DIST-B", "CORP-B")

    def test_geo_less_failure_falls_back_to_scoped_actor_geo(self, geo):
        actor = _staff("writer", "DIST-A", "CORP-A")
        row = _write_audit(
            module_name="staff", endpoint_name="staffcreation", method="POST",
            instance=None, previous_data=None, new_data={}, created_by=str(actor),
            success=False, reason="boom", actor=actor,
        )
        row.refresh_from_db()
        assert (row.district, row.corporation) == ("DIST-A", "CORP-A")

    def test_manual_create_is_stamped_server_side(self, api_client, superuser):
        response = api_client.post(
            COMMON_URL,
            {
                "module_name": "masters",
                "endpoint_name": "ward",
                "method": "DOWNLOAD",
                "new_data": {"action": "download_template"},
                # Client-supplied identity/scope must be ignored.
                "createdBy": "someone-else",
                "created_by_id": "FORGED",
                "district": "DIST-B",
                "success": False,
            },
            format="json",
            HTTP_USER_AGENT="pytest-agent",
        )
        assert response.status_code == 201, response.data
        row = CommonAudit.objects.get(pk=response.data["uuid"])
        assert row.createdBy == str(superuser)
        assert row.created_by_id == superuser.unique_id
        assert row.created_by_type == "super_admin"
        assert row.district is None
        assert row.success is True
        assert row.user_agent == "pytest-agent"

    def test_trail_is_append_only(self, api_client):
        row = _audit()
        assert api_client.patch(f"{COMMON_URL}{row.pk}/", {"reason": "x"}, format="json").status_code == 405
        assert api_client.delete(f"{COMMON_URL}{row.pk}/").status_code == 405
        assert CommonAudit.objects.filter(pk=row.pk).exists()


@pytest.mark.django_db
class TestCommonAuditList:
    def test_filters_and_resolved_names(self, api_client, geo):
        _audit(district="DIST-A", corporation="CORP-A", created_by_id="STC-1",
               created_by_name="Asha", method="POST")
        _audit(district="DIST-B", corporation="CORP-B", success=False, method="DELETE",
               createdBy="legacy-user")

        rows = _get(api_client, COMMON_URL, {"success": "false"})
        assert len(rows) == 1
        assert rows[0]["district_name"] == "Beta District"
        assert rows[0]["local_body_name"] == "Beta Corporation"
        assert rows[0]["local_body_level"] == "Corporation"
        # Legacy rows with no actor name fall back to createdBy.
        assert rows[0]["created_by_name"] == "legacy-user"

        assert len(_get(api_client, COMMON_URL, {"created_by_id": "STC-1"})) == 1
        assert len(_get(api_client, COMMON_URL, {"method": "delete"})) == 1
        assert len(_get(api_client, COMMON_URL, {"district_id": "DIST-A"})) == 1
        assert len(_get(api_client, COMMON_URL, {"local_body_id": "CORP-B"})) == 1
        assert len(_get(api_client, COMMON_URL, {"search": "Asha"})) == 1

    def test_filter_options(self, api_client, geo):
        _audit(district="DIST-A", corporation="CORP-A", created_by_id="STC-1", created_by_name="Asha")
        _audit(district="DIST-B", corporation="CORP-B", module_name="staff", method="PATCH")

        data = api_client.get(f"{COMMON_URL}filter-options/").json()
        assert [d["name"] for d in data["districts"]] == ["Alpha District", "Beta District"]
        assert {b["unique_id"] for b in data["local_bodies"]} == {"CORP-A", "CORP-B"}
        assert data["modules"] == ["masters", "staff"]
        assert data["methods"] == ["PATCH", "POST"]
        assert data["users"] == [{"unique_id": "STC-1", "name": "Asha"}]

        narrowed = api_client.get(f"{COMMON_URL}filter-options/", {"district_id": "DIST-A"}).json()
        assert [b["unique_id"] for b in narrowed["local_bodies"]] == ["CORP-A"]

    def test_scoped_staff_sees_only_own_local_body(self, geo):
        staff = _scoped(_staff("viewer", "DIST-A", "CORP-A"),
                        state="ST-1", district="DIST-A", corporation_ids=["CORP-A"])
        own = _audit(district="DIST-A", corporation="CORP-A")
        _audit(district="DIST-B", corporation="CORP-B")

        rows = _list(CommonAuditViewSet, staff)
        assert [r["uuid"] for r in rows] == [own.uuid]
        # A geo param can only narrow inside the scope, never widen it.
        assert _list(CommonAuditViewSet, staff, {"local_body_id": "CORP-B"}) == []

        options = _list(CommonAuditViewSet, staff, action="filter_options")
        assert [b["unique_id"] for b in options["local_bodies"]] == ["CORP-A"]

    def test_district_scope_is_not_widened_to_state(self, geo):
        staff = _scoped(_staff("district-officer", "DIST-A", None),
                        state="ST-1", district="DIST-A")
        own = _audit(state="ST-1", district="DIST-A")
        _audit(state="ST-1", district="DIST-B")

        assert [r["uuid"] for r in _list(CommonAuditViewSet, staff)] == [own.uuid]

    def test_unscoped_staff_sees_nothing(self, geo):
        staff = _staff("loose", "DIST-A", "CORP-A")
        _audit(district="DIST-A", corporation="CORP-A")
        assert _list(CommonAuditViewSet, staff) == []


@pytest.mark.django_db
class TestLoginAudit:
    def _login(self, **fields):
        defaults = {"module_name": "staff", "username": "x", "success": True}
        defaults.update(fields)
        return LoginAudit.objects.create(**defaults)

    def test_superuser_filters_and_resolved_user(self, api_client, geo):
        member = _staff("member", "DIST-A", "CORP-A")
        self._login(user_unique_id=member.staff_unique_id, username="member")
        self._login(username="ghost", success=False, reason="Invalid credentials")

        rows = _get(api_client, LOGIN_URL, {"success": "true"})
        assert len(rows) == 1
        assert rows[0]["user_name"] == "Member Person"
        assert rows[0]["district_name"] == "Alpha District"
        assert rows[0]["local_body_name"] == "Alpha Corporation"
        assert "password" not in rows[0]

        assert len(_get(api_client, LOGIN_URL, {"success": "false"})) == 1
        assert len(_get(api_client, LOGIN_URL, {"date_from": "2000-01-01"})) == 2
        assert len(_get(api_client, LOGIN_URL, {"date_to": "2000-01-01"})) == 0
        assert len(_get(api_client, LOGIN_URL, {"search": "Invalid"})) == 1

    def test_scoped_staff_sees_only_logins_inside_scope(self, geo):
        viewer = _scoped(_staff("viewer", "DIST-A", "CORP-A"),
                         state="ST-1", district="DIST-A", corporation_ids=["CORP-A"])
        colleague = _staff("colleague", "DIST-A", "CORP-A")
        outsider = _staff("outsider", "DIST-B", "CORP-B")
        inside = self._login(user_unique_id=colleague.staff_unique_id, username="colleague")
        failed_inside = self._login(username="colleague", success=False)
        self._login(user_unique_id=outsider.staff_unique_id, username="outsider")
        self._login(username="outsider", success=False)

        ids = {r["unique_id"] for r in _list(LoginAuditViewSet, viewer)}
        assert ids == {inside.unique_id, failed_inside.unique_id}

    def test_unscoped_staff_sees_nothing(self, geo):
        viewer = _staff("loose", "DIST-A", "CORP-A")
        self._login(user_unique_id=viewer.staff_unique_id, username="loose")
        assert _list(LoginAuditViewSet, viewer) == []
