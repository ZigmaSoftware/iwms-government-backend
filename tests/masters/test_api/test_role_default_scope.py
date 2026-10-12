"""Role defaults are app-only and never leak into web permissions.

A supervisor login resolves exactly the configured modules — no auto-added
Schedule Setup / Daily Operations — whether or not a Staff Access
Configuration exists. The mobile baseline is layered separately when the
login payload builds `app_screens`.
"""
import pytest

from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreenpermission import UserScreenPermission
from app.utils.permission_response import resolve_intersected_permission_payload


@pytest.fixture
def view_action(db):
    return UserScreenAction.objects.create(action_name="view", variable_name="view")


def _make_screen(main_name, screen_name, order=1):
    main, _ = MainScreen.objects.get_or_create(
        mainscreen_name=main_name,
        defaults={
            "mainscreentype_id": "MT-TEST",
            "icon_name": f"{main_name}-icon",
            "order_no": order,
        },
    )
    screen, _ = UserScreen.objects.get_or_create(
        userscreen_name=screen_name,
        defaults={
            "mainscreen_id": main.unique_id,
            "folder_name": f"{screen_name}-folder",
            "icon_name": f"{screen_name}-icon",
            "order_no": order,
        },
    )
    return main, screen


def _grant(owner_kind, staff_id, main, screen, action_id, order=1):
    return UserScreenPermission.objects.create(
        permission_owner_kind=owner_kind,
        staff_id=staff_id,
        local_body_type="panchayat",
        local_body_id="PLB-1",
        mainscreen_id=main.unique_id,
        userscreen_id=screen.unique_id,
        userscreenaction_id=action_id,
        order_no=order,
        is_active=True,
    )


@pytest.mark.django_db
def test_configured_supervisor_gets_only_configured_modules(view_action):
    main, screen = _make_screen("masters", "my-screen")
    _grant("super_admin", None, main, screen, view_action.unique_id)
    _grant("staff", "STAFF-1", main, screen, view_action.unique_id)

    payload = resolve_intersected_permission_payload(
        local_body_type="panchayat",
        local_body_id="PLB-1",
        staff_id="STAFF-1",
        role_name="panchayat_supervisor",
    )
    modules = payload["permissions"]
    assert set(modules) == {"masters"}, modules
    assert "schedule-setup" not in modules
    assert "daily-operations" not in modules


@pytest.mark.django_db
def test_unconfigured_supervisor_gets_no_web_defaults():
    payload = resolve_intersected_permission_payload(
        local_body_type="panchayat",
        local_body_id="PLB-1",
        staff_id="STAFF-NOBODY",
        role_name="panchayat_supervisor",
    )
    modules = payload["permissions"]
    assert "schedule-setup" not in modules
    assert "daily-operations" not in modules
