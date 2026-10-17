"""Audit Dashboard (app/services/audit_dashboard.py and
app/viewsets/superadmin/audits/audit_dashboard_viewset.py).

The viewset is driven through as_view() so the tests do not depend on the
audits/audit-dashboard route being registered."""
from datetime import timedelta

import pytest
from django.core.cache import caches
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.core_modules.complaint_management import (
    ComplaintCategory,
    ComplaintEscalationHistory,
    ComplaintPriority,
    ComplaintStatus,
    ComplaintTicket,
)
from app.models.masters.corporation import Corporation
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.district import District
from app.models.superadmin.audits.login_audit import LoginAudit
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.staff_management.staff_data_scope import StaffDataScope
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.auth_user import User
from app.services.audit_dashboard import DEFAULT_DAYS, LoginTrail, parse_days, window
from app.utils.common_audit import CommonAudit
from app.viewsets.superadmin.audits.audit_dashboard_viewset import AuditDashboardViewSet

URL = "/api/v1/audits/audit-dashboard/"
MINE, OTHER = "DIST-DASH-1", "DIST-DASH-2"


@pytest.fixture(autouse=True)
def _clear_app_cache():
    caches["app_cache"].clear()
    yield
    caches["app_cache"].clear()


@pytest.fixture
def geo(db):
    District.objects.create(unique_id=MINE, state_id="ST-1", name="North District")
    District.objects.create(unique_id=OTHER, state_id="ST-1", name="South District")
    mine = Corporation.objects.create(
        state_id="ST-1", district_id=MINE, area_type_id="AREA-1", corporation_name="Mine Corp"
    )
    other = Corporation.objects.create(
        state_id="ST-1", district_id=OTHER, area_type_id="AREA-1", corporation_name="Other Corp"
    )
    return {"mine": mine, "other": other}


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="dash-admin", is_superuser=True)


@pytest.fixture
def viewer(geo):
    """Staff scoped to the "mine" corporation only."""
    staff = Staffcreation.objects.create(
        username="dash-viewer", employee_name="Viewer", district_id=MINE,
        corporation_id=geo["mine"].unique_id,
    )
    StaffDataScope.objects.create(
        staff_id=staff.staff_unique_id, corporation_ids=[geo["mine"].unique_id], is_active=True
    )
    return staff


@pytest.fixture
def unscoped(db):
    return Staffcreation.objects.create(username="dash-nobody", employee_name="Nobody")


def _get(user, action="summary", status=200, **params):
    view = AuditDashboardViewSet.as_view({"get": action})
    path = {"summary": "summary/", "records": "records/", "filter_options": "filter-options/"}[action]
    request = APIRequestFactory().get(f"{URL}{path}", params)
    force_authenticate(request, user=user)
    response = view(request)
    assert response.status_code == status, response.data
    return response.data


def _at(row, field, when):
    """Backdate an auto_now_add timestamp."""
    type(row).objects.filter(pk=row.pk).update(**{field: when})


def _ago(**kwargs):
    return timezone.now() - timedelta(**kwargs)


def _common(method, corporation, district, when, created_by_id="U-1"):
    return CommonAudit.objects.create(
        module_name="masters", endpoint_name="wards", method=method, object_id="W-1",
        created_by_id=created_by_id, created_by_name=f"Name {created_by_id}",
        district=district, corporation=corporation, createdAt=when,
    )


class TestWindow:
    def test_parse_days(self):
        assert parse_days("7") == 7
        assert parse_days("90") == 90
        assert parse_days("13") == DEFAULT_DAYS
        assert parse_days(None) == DEFAULT_DAYS

    def test_window_is_days_long_and_previous_is_the_same_length(self):
        start_day, end_day, start, end, previous_start = window(7)
        assert (end_day - start_day).days == 6
        assert end - start == timedelta(days=7)
        assert start - previous_start == timedelta(days=7)

    def test_device(self):
        assert LoginTrail.device("Mozilla/5.0 (Linux; Android 14)") == "Android"
        assert LoginTrail.device("Dart/3.1 (dart:io)") == "Mobile app"
        assert LoginTrail.device("") == "Unknown"


@pytest.mark.django_db
class TestCommonTrail:
    @pytest.fixture
    def rows(self, geo):
        mine, other = geo["mine"].unique_id, geo["other"].unique_id
        return [
            _common("POST", mine, MINE, _ago(hours=1)),
            _common("PATCH", mine, MINE, _ago(days=1), created_by_id="U-2"),
            _common("DELETE", other, OTHER, _ago(days=2)),
            _common("DOWNLOAD", other, OTHER, _ago(days=3)),
            # Outside a 7-day window, inside the previous one.
            _common("POST", mine, MINE, _ago(days=10)),
        ]

    def test_superuser_summary(self, admin, rows):
        data = _get(admin, module="common", days=7)
        assert data["kpis"] == {"total": 4, "updates": 1, "deletions": 1, "active_users": 2}
        assert data["previous_total"] == 1
        assert len(data["trend"]) == 7
        assert sum(d["count"] for d in data["trend"]) == 4
        assert {s["key"]: s["count"] for s in data["breakdown"]} == {
            "CREATE": 1, "UPDATE": 1, "DELETE": 1, "OTHER": 1,
        }

    def test_records_have_district_and_local_body(self, admin, rows):
        data = _get(admin, "records", module="common", days=7, page=1, limit=10)
        assert data["count"] == 4
        first = data["results"][0]
        assert first["id"] == rows[0].uuid
        assert first["action"] == "CREATE"
        assert first["user"] == "Name U-1"
        assert first["district"] == "North District"
        assert first["local_body"] == "Mine Corp"

    def test_district_and_local_body_narrow(self, admin, geo, rows):
        assert _get(admin, module="common", days=7, district_id=OTHER)["kpis"]["total"] == 2
        data = _get(admin, module="common", days=7, local_body_id=geo["mine"].unique_id)
        assert data["kpis"]["total"] == 2

    def test_requester_scope(self, viewer, unscoped, rows):
        assert _get(viewer, module="common", days=7)["kpis"]["total"] == 2
        # The scope cannot be widened through the narrowing params.
        assert _get(viewer, module="common", days=7, district_id=OTHER)["kpis"]["total"] == 0
        assert _get(unscoped, module="common", days=7)["kpis"]["total"] == 0

    def test_filter_options(self, admin, viewer, geo, rows):
        data = _get(admin, "filter_options", module="common")
        assert [d["name"] for d in data["districts"]] == ["North District", "South District"]
        assert {lb["unique_id"] for lb in data["local_bodies"]} == {
            geo["mine"].unique_id, geo["other"].unique_id,
        }
        narrowed = _get(admin, "filter_options", module="common", district_id=OTHER)
        assert [lb["name"] for lb in narrowed["local_bodies"]] == ["Other Corp"]
        assert narrowed["local_bodies"][0]["level"] == "Corporation"

        scoped = _get(viewer, "filter_options", module="common")
        assert [d["unique_id"] for d in scoped["districts"]] == [MINE]


@pytest.mark.django_db
class TestLoginTrail:
    @pytest.fixture
    def rows(self, geo, viewer):
        outsider = Staffcreation.objects.create(
            username="outsider", employee_name="Outsider", district_id=OTHER,
            corporation_id=geo["other"].unique_id,
        )
        customer = CustomerCreation.objects.create(
            customer_name="Citizen", username="citizen", district_id=MINE,
            corporation_id=geo["mine"].unique_id,
        )
        logins = [
            LoginAudit.objects.create(
                user_unique_id=viewer.staff_unique_id, username="dash-viewer", success=True,
                user_agent="Mozilla/5.0 (Linux; Android 14)",
            ),
            # A failed attempt is matched on the username tried.
            LoginAudit.objects.create(username="dash-viewer", success=False, reason="Bad password"),
            LoginAudit.objects.create(
                user_unique_id=customer.unique_id, username="citizen", success=True
            ),
            LoginAudit.objects.create(
                user_unique_id=outsider.staff_unique_id, username="outsider", success=True
            ),
        ]
        for index, row in enumerate(logins):
            _at(row, "timestamp", _ago(hours=index + 1))
        return logins

    def test_superuser_summary(self, admin, rows):
        data = _get(admin, module="login", days=7)
        assert data["kpis"] == {"total": 4, "success_rate": 75, "failed": 1, "unique_users": 3}
        assert {s["key"]: s["count"] for s in data["breakdown"]} == {"SUCCESS": 3, "FAILED": 1}

    def test_records_resolve_the_account_geo(self, admin, rows):
        results = _get(admin, "records", module="login", days=7, limit=10)["results"]
        assert [r["id"] for r in results] == [r.unique_id for r in rows]
        assert results[0]["device"] == "Android"
        assert results[1]["status"] == "FAILED"
        assert results[1]["local_body"] == "Mine Corp"
        assert results[3]["district"] == "South District"

    def test_requester_scope_and_narrowing(self, admin, viewer, unscoped, geo, rows):
        assert _get(viewer, module="login", days=7)["kpis"]["total"] == 3
        assert _get(unscoped, module="login", days=7)["kpis"]["total"] == 0
        assert _get(admin, module="login", days=7, district_id=OTHER)["kpis"]["total"] == 1
        narrowed = _get(admin, module="login", days=7, local_body_id=geo["mine"].unique_id)
        assert narrowed["kpis"]["total"] == 3

    def test_filter_options(self, admin, rows):
        data = _get(admin, "filter_options", module="login")
        assert [d["unique_id"] for d in data["districts"]] == [MINE, OTHER]


@pytest.mark.django_db
class TestAccessTrail:
    @pytest.fixture
    def rows(self, geo):
        def grant(local_body, district, action, old, new, when):
            row = PermissionAuditLog.objects.create(
                source="LOCAL_BODY_SCREEN", local_body_type="corporation",
                local_body_id=local_body.unique_id, district_id=district,
                action_type=action, old_permissions=old, new_permissions=new,
            )
            _at(row, "timestamp", when)
            return row

        apps = lambda *ids: {  # noqa: E731
            "app_modules": [{"id": i, "name": i} for i in ids], "modules": [], "widgets": [],
        }
        return [
            grant(geo["mine"], MINE, "CREATED", apps(), apps("A", "B"), _ago(hours=1)),
            grant(geo["mine"], MINE, "UPDATED", apps("A", "B"), apps("A", "C"), _ago(days=1)),
            # A legacy per-grant row: no district of its own.
            grant(geo["other"], None, "DELETED", None, None, _ago(days=2)),
        ]

    def test_superuser_summary(self, admin, rows):
        data = _get(admin, module="access", days=7)
        assert data["kpis"] == {"total": 3, "created": 1, "updated": 1, "deleted": 1}
        assert data["breakdown"] == [
            {"key": "LOCAL_BODY_SCREEN", "label": "Local Body Screen Permission", "count": 3},
        ]

    def test_records_reuse_the_audit_serializer(self, admin, rows):
        results = _get(admin, "records", module="access", days=7, limit=10)["results"]
        assert [r["id"] for r in results] == [r.pk for r in rows]
        assert (results[0]["granted"], results[0]["revoked"]) == (2, 0)
        assert (results[1]["granted"], results[1]["revoked"]) == (1, 1)
        assert results[2]["granted"] is None
        assert results[0]["local_body"] == "Mine Corp"
        assert results[0]["district"] == "North District"
        assert results[0]["source_label"] == "Local Body Screen Permission"

    def test_requester_scope_and_narrowing(self, admin, viewer, unscoped, rows):
        assert _get(viewer, module="access", days=7)["kpis"]["total"] == 2
        assert _get(unscoped, module="access", days=7)["kpis"]["total"] == 0
        # The legacy row is matched through its local body's district.
        assert _get(admin, module="access", days=7, district_id=OTHER)["kpis"]["total"] == 1


@pytest.mark.django_db
class TestComplaintTrail:
    @pytest.fixture
    def rows(self, geo):
        statuses = {
            code: ComplaintStatus.objects.create(status_code=code, status_name=code.title(), sort_order=i)
            for i, code in enumerate(("SUBMITTED", "RESOLVED"))
        }
        priority = ComplaintPriority.objects.create(priority_code="P2", priority_name="High")
        category = ComplaintCategory.objects.create(
            category_code="GARBAGE", category_name="Garbage", default_priority_id=priority.unique_id
        )

        def ticket(district, corporation, status, created, resolved=None):
            row = ComplaintTicket.objects.create(
                category_id=category.unique_id, priority_id=priority.unique_id,
                status_id=statuses[status].unique_id, district_id=district,
                corporation_id=corporation.unique_id, title="Garbage", profile_name="Citizen",
            )
            ComplaintTicket.objects.filter(pk=row.pk).update(created=created, resolved_at=resolved)
            row.refresh_from_db()
            return row

        created = _ago(days=1)
        resolved = ticket(MINE, geo["mine"], "RESOLVED", created, created + timedelta(hours=4))
        open_ = ticket(OTHER, geo["other"], "SUBMITTED", _ago(days=2))
        ComplaintEscalationHistory.objects.create(ticket_id=open_.unique_id, escalation_level=1)
        return [resolved, open_]

    def test_superuser_summary(self, admin, rows):
        data = _get(admin, module="complaint", days=7)
        assert data["kpis"] == {
            "total": 2, "resolved_rate": 50, "avg_resolution_hours": 4.0, "escalated": 1,
        }
        assert {s["key"]: s["label"] for s in data["breakdown"]} == {
            "RESOLVED": "Resolved", "SUBMITTED": "Submitted",
        }

    def test_records_use_district_and_local_body(self, admin, rows):
        results = _get(admin, "records", module="complaint", days=7, limit=10)["results"]
        assert [r["id"] for r in results] == [t.unique_id for t in rows]
        assert results[0]["tat_hours"] == 4 and results[0]["resolved"] is True
        assert results[0]["local_body"] == "Mine Corp"
        assert results[1]["district"] == "South District"
        assert results[1]["resolved"] is False

    def test_narrowing_and_search(self, admin, geo, rows):
        assert _get(admin, module="complaint", days=7, district_id=OTHER)["kpis"]["total"] == 1
        data = _get(
            admin, "records", module="complaint", days=7, search=rows[0].ticket_no,
            local_body_id=geo["mine"].unique_id,
        )
        assert [r["id"] for r in data["results"]] == [rows[0].unique_id]

    def test_staff_scope(self, unscoped, rows):
        # A staff member who neither holds nor held a ticket sees none.
        assert _get(unscoped, module="complaint", days=7)["kpis"]["total"] == 0


@pytest.mark.django_db
def test_unknown_module_is_rejected(admin):
    data = _get(admin, module="route", status=400)
    assert "module" in data
