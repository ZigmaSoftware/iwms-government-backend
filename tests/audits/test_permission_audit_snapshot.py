"""User Access Audit: one PermissionAuditLog row per access save, holding the
access before and after it (app/utils/permission_snapshot.py).

Writes go through the custom bulk-sync / staff-app-modules actions, which do
not touch the staff_audit table the test database lacks (see
tests/superadmin_masters/test_api/test_state_cache.py).
"""
import jwt
import pytest
from django.conf import settings
from django.core.cache import caches
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from app.models.masters.corporation import Corporation
from app.models.masters.customer_masters.customer_access_configuration import (
    CustomerAccessConfiguration,
)
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreenpermission import UserScreenPermission
from app.models.superadmin.staff_management.staff_data_scope import StaffDataScope
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.auth_user import User
from app.utils.permission_snapshot import (
    EMPTY_SNAPSHOT,
    customer_access_snapshot,
    snapshot_from_keys,
    snapshot_keys,
    write_customer_access_audit,
)
from app.viewsets.superadmin.audits.permission_audit_viewset import PermissionAuditLogViewSet

PERMS = "/api/v1/screen-managements/userscreenpermissions/"
WIDGETS = "/api/v1/screen-managements/dashboard-widget-permissions/"
STAFF_APPS = "/api/v1/user-creations/staff-access-configuration/staff-app-modules/"
AUDIT = "/api/v1/audits/permission-audit/"


@pytest.fixture(autouse=True)
def _clear_app_cache():
    caches["app_cache"].clear()
    yield
    caches["app_cache"].clear()


@pytest.fixture
def admin(db):
    return User.objects.create_user(username="perm-audit-admin", is_superuser=True)


@pytest.fixture
def api_client(admin):
    token = jwt.encode({"unique_id": admin.unique_id}, settings.SECRET_KEY, algorithm="HS256")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def screens(db):
    module = MainScreen.objects.create(
        mainscreentype_id="MST-1", mainscreen_name="masters", icon_name="ic-m", order_no=1
    )
    wards = UserScreen.objects.create(
        mainscreen_id=module.unique_id,
        userscreen_name="wards",
        folder_name="wards",
        icon_name="ic-w",
        order_no=1,
    )
    add = UserScreenAction.objects.create(action_name="add", variable_name="add")
    edit = UserScreenAction.objects.create(action_name="edit", variable_name="edit")
    return {"module": module, "wards": wards, "add": add, "edit": edit}


def _corporation(name, district="DIST-1"):
    return Corporation.objects.create(
        state_id="STATE-1", district_id=district, area_type_id="AREA-1", corporation_name=name
    )


def _sync(client, corp, screens, action_ids):
    return client.post(
        f"{PERMS}bulk-sync-multi-localbody/corporation/{corp.unique_id}/",
        {
            "mainScreenId": screens["module"].unique_id,
            "userScreens": [
                {"userScreenId": screens["wards"].unique_id, "actionIds": action_ids}
            ],
        },
        format="json",
    )


@pytest.mark.django_db
class TestSnapshotKeys:
    def test_round_trip_keeps_every_kind_of_grant(self, screens):
        app = AppModule.objects.create(
            module_key="driver", surface_key="driver", label="Driver", route="/driver"
        )
        keys = {
            ("app", app.unique_id),
            ("action", screens["wards"].unique_id, screens["add"].unique_id),
            ("column", screens["wards"].unique_id, "COL-1", "READ_ONLY"),
            ("widget", "trip_summary"),
        }
        snapshot = snapshot_from_keys(keys)

        assert snapshot_keys(snapshot) == keys
        assert snapshot["app_modules"] == [{"id": app.unique_id, "name": "Driver"}]
        assert snapshot["widgets"] == [{"id": "trip_summary", "name": "Trip Summary"}]
        screen = snapshot["modules"][0]["screens"][0]
        assert snapshot["modules"][0]["name"] == "masters"
        assert screen["name"] == "wards"
        assert screen["actions"] == [{"id": screens["add"].unique_id, "name": "add"}]
        assert screen["columns"][0]["state"] == "READ_ONLY"


@pytest.mark.django_db
class TestLocalBodyScreenSaves:
    def test_bulk_sync_writes_one_snapshot_row_per_save(self, api_client, admin, screens):
        corp = _corporation("Chennai")

        assert _sync(api_client, corp, screens, [screens["add"].unique_id, screens["edit"].unique_id]).status_code == 200
        assert _sync(api_client, corp, screens, [screens["add"].unique_id]).status_code == 200

        rows = list(PermissionAuditLog.objects.order_by("id"))
        # No per-grant GRANT_CHANGE rows on top of the snapshot rows.
        assert [r.source for r in rows] == ["LOCAL_BODY_SCREEN", "LOCAL_BODY_SCREEN"]
        created, updated = rows
        assert created.action_type == "CREATED"
        assert created.http_method == "POST"
        assert created.local_body_type == "corporation"
        assert created.local_body_id == corp.unique_id
        assert created.permission_owner_kind == "super_admin"
        assert created.mainscreen_id == screens["module"].unique_id
        assert created.updated_by_id == admin.unique_id
        assert snapshot_keys(created.old_permissions) == set()

        assert updated.action_type == "UPDATED"
        old, new = snapshot_keys(updated.old_permissions), snapshot_keys(updated.new_permissions)
        assert old - new == {("action", screens["wards"].unique_id, screens["edit"].unique_id)}
        assert new - old == set()

    def test_delete_by_local_body_is_a_deleted_row(self, api_client, screens):
        corp = _corporation("Madurai")
        _sync(api_client, corp, screens, [screens["add"].unique_id])

        response = api_client.delete(
            f"{PERMS}delete-by-localbody/corporation/{corp.unique_id}/"
            f"?mainscreen_id={screens['module'].unique_id}"
        )

        assert response.status_code == 200
        row = PermissionAuditLog.objects.order_by("-id").first()
        assert row.source == "LOCAL_BODY_SCREEN"
        assert row.action_type == "DELETED"
        assert row.http_method == "DELETE"
        assert snapshot_keys(row.new_permissions) == set()

    def test_dashboard_widgets_are_part_of_the_local_body_snapshot(self, api_client):
        corp = _corporation("Salem")

        response = api_client.post(
            f"{WIDGETS}bulk-sync-by-localbody/corporation/{corp.unique_id}/",
            {"widgets": [{"widgetName": "trip_summary", "isEnabled": True}]},
            format="json",
        )

        assert response.status_code == 200
        row = PermissionAuditLog.objects.get()
        assert row.source == "LOCAL_BODY_SCREEN"
        assert snapshot_keys(row.new_permissions) == {("widget", "trip_summary")}

    def test_writes_outside_a_request_still_get_per_grant_rows(self, screens):
        UserScreenPermission.objects.create(
            local_body_type="corporation",
            local_body_id="CORP-X",
            permission_owner_kind="super_admin",
            mainscreen_id=screens["module"].unique_id,
            userscreen_id=screens["wards"].unique_id,
            userscreenaction_id=screens["add"].unique_id,
            order_no=1,
        )
        row = PermissionAuditLog.objects.get()
        assert row.source == "GRANT_CHANGE"
        assert row.old_permissions is None


@pytest.mark.django_db
class TestPersonAccessSaves:
    def test_staff_app_modules_save_is_a_staff_access_row(self, api_client, admin):
        staff = Staffcreation.objects.create(
            username="driver-1", employee_name="Driver One", corporation_id="CORP-1",
            district_id="DIST-1",
        )
        app = AppModule.objects.create(
            module_key="driver", surface_key="driver", label="Driver", route="/driver"
        )

        response = api_client.post(
            STAFF_APPS,
            {"staff_id": staff.staff_unique_id, "app_module_ids": [app.unique_id]},
            format="json",
        )

        assert response.status_code == 200
        row = PermissionAuditLog.objects.get()
        assert row.source == "STAFF_ACCESS"
        assert row.target_id == staff.staff_unique_id
        assert row.staff_id == staff.staff_unique_id
        assert row.local_body_type == "corporation"
        assert row.local_body_id == "CORP-1"
        assert row.action_type == "CREATED"
        assert row.updated_by_id == admin.unique_id
        assert snapshot_keys(row.new_permissions) == {("app", app.unique_id)}

    def test_customer_access_snapshot_row(self, screens):
        config = CustomerAccessConfiguration.objects.create(
            customer_id="CUST-1", app_screen_ids=[screens["wards"].unique_id]
        )
        write_customer_access_audit(
            None, config, EMPTY_SNAPSHOT, customer_access_snapshot(config), "CREATED"
        )
        row = PermissionAuditLog.objects.get()
        assert row.source == "CUSTOMER_ACCESS"
        assert row.target_id == "CUST-1"
        assert snapshot_keys(row.new_permissions) == {("screen", screens["wards"].unique_id)}


@pytest.mark.django_db
class TestAuditEndpoints:
    def test_list_is_lean_and_detail_has_the_snapshots(self, api_client, screens):
        corp = _corporation("Trichy")
        _sync(api_client, corp, screens, [screens["add"].unique_id])
        row = PermissionAuditLog.objects.get()

        listing = api_client.get(AUDIT, {"page": 1, "limit": 10})
        assert listing.status_code == 200
        item = listing.json()["results"][0]
        assert "new_permissions" not in item
        assert item["source_label"] == "Local Body Screen Permission"
        assert item["granted_count"] == 1
        assert item["revoked_count"] == 0
        assert item["changed_modules"] == ["masters"]
        assert item["local_body_name"] == "Trichy"

        detail = api_client.get(f"{AUDIT}{row.pk}/")
        assert detail.status_code == 200
        assert detail.json()["new_permissions"]["modules"][0]["name"] == "masters"

    def test_source_filter_keeps_legacy_rows_and_options_list_sources(self, api_client):
        PermissionAuditLog.objects.create(
            source="GRANT_CHANGE", permission_owner_kind="staff", staff_id="STC-1"
        )
        PermissionAuditLog.objects.create(
            source="GRANT_CHANGE", permission_owner_kind="super_admin",
            local_body_type="corporation", local_body_id="CORP-1",
        )

        staff_rows = api_client.get(AUDIT, {"source": "STAFF_ACCESS", "limit": 10}).json()["results"]
        assert [r["staff_id"] for r in staff_rows] == ["STC-1"]

        options = api_client.get(f"{AUDIT}filter-options/").json()
        assert {o["unique_id"] for o in options["sources"]} == set(
            PermissionAuditLog.CURRENT_SOURCES
        )
        assert [o["unique_id"] for o in options["local_bodies"]] == ["CORP-1"]

    def test_scoped_staff_sees_only_their_local_body(self, db):
        mine, other = _corporation("Mine"), _corporation("Other", district="DIST-2")
        PermissionAuditLog.objects.create(
            source="LOCAL_BODY_SCREEN", local_body_type="corporation", local_body_id=mine.unique_id
        )
        PermissionAuditLog.objects.create(
            source="LOCAL_BODY_SCREEN", local_body_type="corporation", local_body_id=other.unique_id
        )
        viewer = Staffcreation.objects.create(username="viewer", employee_name="Viewer")
        StaffDataScope.objects.create(
            staff_id=viewer.staff_unique_id, corporation_ids=[mine.unique_id], is_active=True
        )
        unscoped = Staffcreation.objects.create(username="nobody", employee_name="Nobody")

        def visible(user):
            request = APIRequestFactory().get(AUDIT, {"limit": 10})
            force_authenticate(request, user=user)
            response = PermissionAuditLogViewSet.as_view({"get": "list"})(request)
            return [r["local_body_id"] for r in response.data["results"]]

        district_viewer = Staffcreation.objects.create(username="dist", employee_name="District")
        StaffDataScope.objects.create(
            staff_id=district_viewer.staff_unique_id, district="DIST-2", is_active=True
        )

        assert visible(viewer) == [mine.unique_id]
        # A District-level scope covers the local bodies inside the district.
        assert visible(district_viewer) == [other.unique_id]
        assert visible(unscoped) == []
