"""The permission catalog, screen dependencies and the middleware that reads them.

Every module and screen is named after the admin sidebar ("Daily Operations"
is `daily-operations`, its "Daily Trip Plan" entry is `daily-trip-plan`), and
ONE grant on a page covers every table that page is built from.
"""
from types import SimpleNamespace

import pytest
from django.test import RequestFactory

from app.middleware import module_permission_middleware as mpm
from app.utils.app_feature_grants import ROLE_SCREEN_TEMPLATES, SCREEN_PERMISSIONS
from app.utils.permission_catalog import (
    LEGACY_MODULE_NAMES,
    LEGACY_SCREEN_NAMES,
    ROUTE_OWNERS,
    SCREEN_STRUCTURE,
)
from app.utils.permission_response import normalize_permission_names
from app.utils.screen_dependencies import SCREEN_DEPENDENCIES

DAILY_TRIP_TABLES = (
    "daily-trip-assignments",
    "daily-trip-collection-points",
    "daily-trip-household-collections",
)
CATALOG_SCREENS = {(m, s) for m, screens in SCREEN_STRUCTURE.items() for s in screens}


# ---------------------------------------------------------------- catalog

def test_daily_trip_plan_owns_its_three_tables():
    for table in DAILY_TRIP_TABLES:
        assert ROUTE_OWNERS[f"schedule-operations/{table}"] == (
            "daily-operations",
            "daily-trip-plan",
        )


def test_every_sidebar_entry_is_a_screen():
    # Frontend-only pages are screens too, so "view" on them can be granted.
    for screen in [
        ("dashboard", "dashboard"),
        ("customer-masters", "apartment-list"),
        ("daily-operations", "daily-trip-tracking"),
        ("complaint-management", "reference-data"),
        ("complaint-reports", "complaints-report"),
    ]:
        assert screen in CATALOG_SCREENS


def test_leader_logins_are_owned_by_leader_management_screens():
    assert ROUTE_OWNERS["masters/panchayat-leaders"] == (
        "leader-management", "plb-leader-creation",
    )
    assert ROUTE_OWNERS["masters/state-leaders"] == (
        "leader-management", "state-leader-creation",
    )


def test_old_names_map_to_sidebar_names():
    assert LEGACY_MODULE_NAMES["schedule-operations"] == "daily-operations"
    assert LEGACY_SCREEN_NAMES["daily-trip-plans"] == "daily-trip-plan"
    assert LEGACY_SCREEN_NAMES["priorities"] == "reference-data"


def test_code_only_names_catalog_screens():
    # Role templates, mobile visibility rules and screen dependencies are
    # resolved by name; a name the seeder does not create grants nothing.
    for role, modules in ROLE_SCREEN_TEMPLATES.items():
        for module_name, screens in modules.items():
            for screen_name in screens:
                assert (module_name, screen_name) in CATALOG_SCREENS, role
    for key, requirement in SCREEN_PERMISSIONS.items():
        if requirement:
            assert requirement[:2] in CATALOG_SCREENS, key
    for owner in SCREEN_DEPENDENCIES:
        assert owner in CATALOG_SCREENS


def test_legacy_permission_maps_are_renamed():
    normalized = normalize_permission_names({
        "schedule-operations": {"daily-trip-plans": ["view"], "daily-trip-assignments": ["edit"]},
        "complaint-ticket": {"priorities": ["add"], "complaints-report": ["view"]},
    })
    assert normalized == {
        "daily-operations": {"daily-trip-plan": ["view", "edit"]},
        "complaint-management": {"reference-data": ["add"]},
        "complaint-reports": {"complaints-report": ["view"]},
    }


# ------------------------------------------------------------- middleware

class _View:
    pass


def _call(monkeypatch, method, path, permissions, resource="Anything"):
    """Run the middleware for a non-superuser holding `permissions`."""
    view_class = type(f"{resource}ViewSet", (_View,), {"permission_resource": resource})
    view_func = SimpleNamespace(cls=view_class, actions={})
    request = getattr(RequestFactory(), method.lower())(path)

    def _auth(req):
        req.user = SimpleNamespace(is_superuser=False)
        return None

    monkeypatch.setattr(mpm, "_authenticate_request", _auth)
    monkeypatch.setattr(mpm, "_resolve_permissions_for_request", lambda req: permissions)
    return mpm.ModulePermissionMiddleware(lambda r: None).process_view(
        request, view_func, (), {}
    )


DAILY_TRIP_PLAN_GRANT = {"daily-operations": {"daily-trip-plan": ["view", "edit"]}}


@pytest.mark.parametrize("table,resource", [
    ("daily-trip-assignments", "DailyTripAssignment"),
    ("daily-trip-collection-points", "DailyTripCollectionPoint"),
    ("daily-trip-household-collections", "DailyTripHouseholdCollection"),
])
def test_daily_trip_plan_grant_covers_each_table(monkeypatch, table, resource):
    path = f"/api/v1/schedule-operations/{table}/abc/"
    assert _call(monkeypatch, "GET", path, DAILY_TRIP_PLAN_GRANT, resource) is None
    assert _call(monkeypatch, "PATCH", path, DAILY_TRIP_PLAN_GRANT, resource) is None
    # Delete was not granted, so no table gets it.
    assert _call(monkeypatch, "DELETE", path, DAILY_TRIP_PLAN_GRANT, resource).status_code == 403


def test_daily_trip_plan_lookups_are_read_only(monkeypatch):
    path = "/api/v1/customer-masters/customercreations/"
    assert _call(monkeypatch, "GET", path, DAILY_TRIP_PLAN_GRANT, "CustomerCreation") is None
    assert _call(monkeypatch, "POST", path, DAILY_TRIP_PLAN_GRANT, "CustomerCreation").status_code == 403


def test_frontend_only_page_reads_its_data(monkeypatch):
    grant = {"daily-operations": {"daily-trip-tracking": ["view"]}}
    path = "/api/v1/schedule-operations/daily-trip-collection-points/"
    assert _call(monkeypatch, "GET", path, grant, "DailyTripCollectionPoint") is None
    assert _call(monkeypatch, "PATCH", path + "x/", grant, "DailyTripCollectionPoint").status_code == 403


def test_unrelated_resource_is_still_denied(monkeypatch):
    response = _call(
        monkeypatch, "GET", "/api/v1/user-creations/staffcreation/",
        DAILY_TRIP_PLAN_GRANT, "StaffCreation",
    )
    assert response.status_code == 403


def test_grant_under_old_route_names_still_works(monkeypatch):
    # Grants named after the URL resource keep resolving through the
    # allowlist/alias fallback.
    response = _call(
        monkeypatch, "GET", "/api/v1/schedule-operations/daily-trip-assignments/",
        {"schedule-operations": {"daily-trip-assignments": ["view"]}},
        "DailyTripAssignment",
    )
    assert response is None


def test_leader_management_grant_authorizes_masters_route(monkeypatch):
    response = _call(
        monkeypatch, "POST", "/api/v1/masters/panchayat-leaders/",
        {"leader-management": {"plb-leader-creation": ["add"]}},
        "PanchayatLeaderLogin",
    )
    assert response is None


def test_my_tasks_includes_ticket_writes(monkeypatch):
    response = _call(
        monkeypatch, "POST", "/api/v1/complaint-ticket/tickets/abc/resolve/",
        {"complaint-management": {"my-tasks": ["view", "add"]}},
        "ComplaintTicket",
    )
    assert response is None


@pytest.mark.parametrize("screen,route,resource", [
    ("reference-data", "priorities", "ComplaintPriority"),
    ("reference-data", "statuses", "ComplaintStatus"),
    ("categories", "subcategories", "ComplaintSubcategory"),
])
def test_one_page_grant_covers_its_tabs(monkeypatch, screen, route, resource):
    grant = {"complaint-management": {screen: ["view", "add"]}}
    assert _call(monkeypatch, "POST", f"/api/v1/complaint-ticket/{route}/", grant, resource) is None


def test_reference_data_grant_does_not_cover_categories(monkeypatch):
    response = _call(
        monkeypatch, "POST", "/api/v1/complaint-ticket/categories/",
        {"complaint-management": {"reference-data": ["view", "add"]}},
        "ComplaintCategory",
    )
    assert response.status_code == 403


def test_staff_user_type_grant_covers_all_three_tabs(monkeypatch):
    grant = {"role-management": {"staff-user-type": ["edit"]}}
    for route in ("staffusertypes", "contractorusertypes", "governmentusertypes"):
        assert _call(
            monkeypatch, "PATCH", f"/api/v1/role-assigns/{route}/x/", grant, "StaffUserType"
        ) is None


# ------------------------------------------------------------------ seeder

@pytest.mark.django_db
def test_seeder_renames_rows_and_keeps_grants():
    from app.management.commands.seeders.superadmin.screen_management.permissions import (
        PermissionSeeder,
    )
    from app.models.superadmin.screen_management.mainscreen import MainScreen
    from app.models.superadmin.screen_management.mainscreentype import MainScreenType
    from app.models.superadmin.screen_management.userscreen import UserScreen
    from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
    from app.models.superadmin.screen_management.userscreenpermission import (
        UserScreenPermission,
    )

    megamenu = MainScreenType.objects.create(type_name="megamenu")
    old_main = MainScreen.objects.create(
        mainscreen_name="schedule-operations", mainscreentype_id=megamenu.pk,
        icon_name="schedule-operations", order_no=1,
    )
    old_plan = UserScreen.objects.create(
        mainscreen_id=old_main.pk, userscreen_name="daily-trip-plans",
        folder_name="daily-trip-plans", icon_name="daily-trip-plans", order_no=1,
    )
    complaints = MainScreen.objects.create(
        mainscreen_name="complaint-ticket", mainscreentype_id=megamenu.pk,
        icon_name="complaint-ticket", order_no=2,
    )
    priorities = UserScreen.objects.create(
        mainscreen_id=complaints.pk, userscreen_name="priorities",
        folder_name="priorities", icon_name="priorities", order_no=2,
    )
    view = UserScreenAction.objects.create(action_name="view", variable_name="view")
    for main, screen in ((old_main, old_plan), (complaints, priorities)):
        UserScreenPermission.objects.create(
            staff_id="STF1", permission_owner_kind="staff",
            mainscreen_id=main.pk, userscreen_id=screen.pk, userscreenaction_id=view.pk,
            order_no=1,
        )

    PermissionSeeder().run()

    plan = UserScreen.objects.get(userscreen_name="daily-trip-plan")
    assert plan.pk == old_plan.pk  # renamed in place
    assert MainScreen.objects.get(pk=old_main.pk).mainscreen_name == "daily-operations"
    # The grant rode along with the rename ...
    assert UserScreenPermission.objects.filter(userscreen_id=plan.pk, is_deleted=False).exists()
    # ... the new frontend-only page inherited it ...
    tracking = UserScreen.objects.get(userscreen_name="daily-trip-tracking")
    assert UserScreenPermission.objects.filter(userscreen_id=tracking.pk, is_deleted=False).exists()
    # ... and the folded tab's grant moved onto its page.
    reference = UserScreen.objects.get(userscreen_name="reference-data")
    assert UserScreenPermission.objects.filter(
        userscreen_id=reference.pk, staff_id="STF1", is_deleted=False,
    ).exists()
    assert not UserScreenPermission.objects.filter(
        userscreen_id=priorities.pk, is_deleted=False,
    ).exists()


# ------------------------------------------------- frontend catalog copy

def test_frontend_catalog_copy_is_current():
    from app.utils.permission_catalog_export import FRONTEND_CATALOG_PATH, render_typescript

    if not FRONTEND_CATALOG_PATH.exists():
        pytest.skip("frontend checkout not present")
    assert FRONTEND_CATALOG_PATH.read_text() == render_typescript(), (
        "Run: python manage.py sync_permission_catalog"
    )
