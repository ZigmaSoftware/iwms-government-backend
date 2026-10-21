"""Admin and Superadmin dashboards (app/services/dashboard_metrics.py,
app/viewsets/dashboard_admin_viewset.py, dashboard_superadmin_viewset.py).

Driven through as_view() so the tests do not depend on route registration."""
import pytest
from django.core.cache import caches
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.masters.corporation import Corporation
from app.models.masters.district import District
from app.models.masters.municipality import Municipality
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.ward import Ward
from app.models.superadmin.common_masters.state import State
from app.models.superadmin.staff_management.staff_data_scope import StaffDataScope
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.auth_user import User
from app.viewsets.dashboard_admin_viewset import AdminDashboardViewSet
from app.viewsets.dashboard_superadmin_viewset import SuperadminDashboardViewSet

MINE, OTHER = "DIST-ADM-1", "DIST-ADM-2"


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
        state_id="ST-1", district_id=MINE, area_type_id="AREA-1", corporation_name="Mine Corp",
    )
    other = Corporation.objects.create(
        state_id="ST-1", district_id=OTHER, area_type_id="AREA-1", corporation_name="Other Corp",
    )
    town = Municipality.objects.create(
        state_id="ST-1", district_id=MINE, area_type_id="AREA-1", municipality_name="Mine Town",
    )
    for body, name in ((mine, "Mine Ward"), (other, "Other Ward")):
        Ward.objects.create(
            state_id="ST-1", district_id=body.district_id, area_type_id="AREA-1",
            corporation_id=body.unique_id, ward_name=name,
        )
    for n, body in enumerate((mine, mine, other)):
        VehicleCreation.objects.create(
            vehicle_no=f"TN-{n}", vehicle_type_id="VT-1", fuel_type_id="FUEL-1",
            state_id="ST-1", district_id=body.district_id, area_type_id="AREA-1",
            corporation_id=body.unique_id,
        )
    return {"mine": mine, "other": other, "town": town}


@pytest.fixture
def two_states(geo):
    """geo's ST-1 plus a second state with one corporation and vehicle."""
    State.objects.create(unique_id="ST-1", country_id="IN", name="Home State")
    State.objects.create(unique_id="ST-2", country_id="IN", name="Far State")
    District.objects.create(unique_id="DIST-FAR", state_id="ST-2", name="Far District")
    far = Corporation.objects.create(
        state_id="ST-2", district_id="DIST-FAR", area_type_id="AREA-2", corporation_name="Far Corp",
    )
    VehicleCreation.objects.create(
        vehicle_no="KA-1", vehicle_type_id="VT-1", fuel_type_id="FUEL-1",
        state_id="ST-2", district_id="DIST-FAR", area_type_id="AREA-2",
        corporation_id=far.unique_id,
    )
    return {**geo, "far": far}


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="dash-super", is_superuser=True)


GRANTS = {}


@pytest.fixture(autouse=True)
def _grants(monkeypatch):
    """Screen grants per staff id, in the middleware's payload shape."""
    GRANTS.clear()
    monkeypatch.setattr(
        "app.viewsets.dashboard_admin_viewset._resolve_permissions_for_request",
        lambda request: GRANTS.get(getattr(request.user, "staff_unique_id", None), {}),
    )


def _scoped_staff(geo, username, *, dashboard=True):
    """Staff scoped to the "mine" corporation only."""
    staff = Staffcreation.objects.create(
        username=username, employee_name=username, state_id="ST-1", district_id=MINE,
        corporation_id=geo["mine"].unique_id,
    )
    StaffDataScope.objects.create(
        staff_id=staff.staff_unique_id, corporation_ids=[geo["mine"].unique_id], is_active=True,
    )
    if dashboard:
        GRANTS[staff.staff_unique_id] = {"dashboard": {"dashboard": ["view"]}}
    return staff


@pytest.fixture
def viewer(geo):
    return _scoped_staff(geo, "dash-viewer")


def _get(viewset, user, status=200, **params):
    view = viewset.as_view({"get": "list"})
    request = APIRequestFactory().get("/api/v1/dashboard/x/", params)
    force_authenticate(request, user=user)
    response = view(request)
    assert response.status_code == status, getattr(response, "data", response)
    return response.data


@pytest.mark.django_db
class TestAdminDashboard:
    def test_scoped_staff_sees_only_their_local_body(self, viewer, geo):
        data = _get(AdminDashboardViewSet, viewer)

        mine = geo["mine"].unique_id
        assert [b["id"] for b in data["filters"]["local_bodies"]] == [mine]
        # One local body in scope: it is the selection, nothing to pick.
        assert data["scope"]["local_body_ids"] == [mine]
        assert data["filters"]["can_pick_local_body"] is False
        assert [w["name"] for w in data["filters"]["wards"]] == ["Mine Ward"]
        assert data["fleet"]["total"] == 2
        assert [r["local_body_id"] for r in data["local_bodies"]] == [mine]
        assert data["local_bodies"][0]["vehicles"] == 2

        masters = {row["key"]: row for row in data["masters"]}
        assert masters["corporations"]["total"] == 1
        assert masters["wards"]["total"] == 1
        assert masters["wards"]["breakdown"] == {mine: 1}
        assert masters["vehicles"]["breakdown"] == {mine: 2}

    def test_picking_outside_scope_cannot_widen_it(self, viewer, geo):
        data = _get(AdminDashboardViewSet, viewer, local_body_id=geo["other"].unique_id, district_id=OTHER)

        assert data["scope"]["district_ids"] == []
        assert data["scope"]["local_body_ids"] == [geo["mine"].unique_id]
        assert data["fleet"]["total"] == 2

    def test_super_admin_sees_everything_and_can_pick(self, admin, geo):
        data = _get(AdminDashboardViewSet, admin)

        ids = {b["id"] for b in data["filters"]["local_bodies"]}
        assert ids == {geo["mine"].unique_id, geo["other"].unique_id, geo["town"].unique_id}
        assert data["filters"]["can_pick_local_body"] is True
        assert data["fleet"]["total"] == 3
        # The empty municipality is left out of the comparison table.
        assert {r["local_body_id"] for r in data["local_bodies"]} == {
            geo["mine"].unique_id, geo["other"].unique_id,
        }

        picked = _get(AdminDashboardViewSet, admin, local_body_id=geo["other"].unique_id)
        assert picked["scope"]["local_body_name"] == "Other Corp"
        assert picked["fleet"]["total"] == 1
        assert [w["name"] for w in picked["filters"]["wards"]] == ["Other Ward"]

    def test_district_pick_narrows_local_bodies(self, admin, geo):
        data = _get(AdminDashboardViewSet, admin, district_id=MINE)

        assert data["scope"]["district_name"] == "North District"
        assert data["fleet"]["total"] == 2
        masters = {row["key"]: row for row in data["masters"]}
        assert masters["districts"]["total"] == 1
        assert masters["corporations"]["total"] == 1
        assert masters["municipalities"]["total"] == 1

    def test_state_pick_narrows_districts_and_local_bodies(self, admin, two_states):
        data = _get(AdminDashboardViewSet, admin)
        assert {s["name"] for s in data["filters"]["states"]} == {"Home State", "Far State"}
        assert data["filters"]["can_pick_state"] is True
        assert data["fleet"]["total"] == 4

        far = _get(AdminDashboardViewSet, admin, state_id="ST-2")
        assert far["scope"]["state_name"] == "Far State"
        assert [d["id"] for d in far["filters"]["districts"]] == ["DIST-FAR"]
        assert [b["id"] for b in far["filters"]["local_bodies"]] == [two_states["far"].unique_id]
        assert far["fleet"]["total"] == 1
        # A district of another state is dropped from the pick.
        mixed = _get(AdminDashboardViewSet, admin, state_id="ST-2", district_id=MINE)
        assert mixed["scope"]["district_ids"] == []
        assert mixed["fleet"]["total"] == 1

    def test_staff_without_the_dashboard_grant_are_refused(self, geo):
        staff = _scoped_staff(geo, "dash-nogrant", dashboard=False)
        _get(AdminDashboardViewSet, staff, status=403)

        # A grant on another screen does not open it either.
        GRANTS[staff.staff_unique_id] = {"dashboard": {"dashboard": ["add"]}, "masters": {"wards": ["view"]}}
        _get(AdminDashboardViewSet, staff, status=403)

    def test_non_staff_users_are_refused(self, geo):
        # The requester-scope filter passes non-staff users through
        # unfiltered, so they must not reach the dashboard at all.
        user = User.objects.create_user(username="dash-plain")
        _get(AdminDashboardViewSet, user, status=403)

    def test_date_range_is_echoed(self, viewer):
        data = _get(AdminDashboardViewSet, viewer, from_date="2026-10-01", to_date="2026-10-07")

        assert (data["scope"]["from_date"], data["scope"]["to_date"], data["scope"]["days"]) == (
            "2026-10-01", "2026-10-07", 7,
        )
        assert len(data["daily"]) == 7


@pytest.mark.django_db
class TestSuperadminDashboard:
    def test_breaks_down_per_local_body_and_district(self, admin, viewer, geo):
        data = _get(SuperadminDashboardViewSet, admin)

        assert data["platform"]["local_bodies"] == 3
        assert data["platform"]["local_bodies_by_type"]["Corporation"]["total"] == 2
        rows = {r["local_body_id"]: r for r in data["local_bodies"]}
        assert rows[geo["mine"].unique_id]["vehicles"] == 2
        assert rows[geo["mine"].unique_id]["staff"] == 1
        assert rows[geo["mine"].unique_id]["wards"] == 1
        assert rows[geo["other"].unique_id]["vehicles"] == 1
        assert geo["town"].unique_id not in rows

        districts = {r["district_id"]: r for r in data["districts"]}
        assert districts[MINE]["local_bodies"] == 2
        assert districts[MINE]["vehicles"] == 2
        assert districts[OTHER]["vehicles"] == 1

        masters = {row["key"]: row for row in data["masters"]}
        assert masters["vehicles"]["breakdown"] == {MINE: 2, OTHER: 1}

    def test_state_pick_narrows_every_section(self, admin, two_states):
        data = _get(SuperadminDashboardViewSet, admin, state_id="ST-1")

        assert data["scope"]["state_ids"] == ["ST-1"]
        assert {s["id"] for s in data["filters"]["states"]} == {"ST-1", "ST-2"}
        assert data["platform"]["states"] == 1
        assert data["platform"]["districts"] == 2
        assert data["platform"]["local_bodies"] == 3
        assert data["platform"]["vehicles"] == 3
        assert {r["district_id"] for r in data["districts"]} == {MINE, OTHER}
        assert two_states["far"].unique_id not in {r["local_body_id"] for r in data["local_bodies"]}
        masters = {row["key"]: row for row in data["masters"]}
        assert masters["vehicles"]["total"] == 3

        unfiltered = _get(SuperadminDashboardViewSet, admin)
        assert unfiltered["platform"]["vehicles"] == 4
        assert unfiltered["scope"]["state_name"] == "All states"

    def test_staff_are_refused(self, viewer):
        _get(SuperadminDashboardViewSet, viewer, status=403)

    def test_staff_flagged_superuser_are_refused(self, viewer):
        # Like private's company superusers: a superuser staff record is still
        # a tenant user (role = its staff role), not the platform super admin.
        viewer.is_superuser = True
        viewer.save(update_fields=["is_superuser"])
        _get(SuperadminDashboardViewSet, viewer, status=403)

    def test_non_superuser_platform_account_is_refused(self, geo):
        _get(SuperadminDashboardViewSet, User.objects.create_user(username="dash-platform"), status=403)
