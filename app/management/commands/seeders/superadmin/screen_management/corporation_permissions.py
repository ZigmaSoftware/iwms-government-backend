"""
CorporationPermissionSeeder
===========================

Seeds scoped UserScreenPermission rows for the two demo corporation users
created by ``CorporationAccessSeeder`` (Erode Corporation admin + supervisor).

Login resolves a local-body-scoped staff's permissions as the INTERSECTION of
a ``super_admin`` baseline and the staff's own rows for that local body
(see app/utils/permission_response.py::resolve_intersected_permission_payload),
so this seeder writes, for the Erode-Corporation local body:

  1. a ``super_admin`` baseline row for every screen × {view,add,edit,delete}
     — the ceiling,
  2. Corporation Admin staff rows: full CRUD on every screen,
  3. Corporation Supervisor staff rows: full CRUD on the schedule / daily-trip
     screens, view-only everywhere else (the write ceiling from decision D4).

It also creates the ``view/add/edit/delete`` UserScreenAction rows (nothing
else seeds them). Screen rows themselves are owned by ``PermissionSeeder`` and
must match ``AppSidebar.tsx``.
"""

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.corporation import Corporation
from app.models.superadmin.screen_management.companyuserscreenpermission import UserScreenPermission
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails

ACTIONS = ["view", "add", "edit", "delete"]

# Schedule / daily-trip screens a Corporation Supervisor may WRITE (decision D4).
SCHEDULE_WRITE_SCREENS = {
    "trip-plans",
    "daily-trip-assignments",
    "daily-trip-collection-points",
    "daily-trip-household-collections",
    "daily-trip-logs",
    "secondary-bin-collection-events",
    "vehicle-breakdowns",
}


class CorporationPermissionSeeder(BaseSeeder):
    name = "CorporationPermissionSeeder"

    def run(self):
        corporation = Corporation.objects.filter(
            corporation_name="Erode Corporation", is_deleted=False
        ).first()
        if not corporation:
            self.log("Corporation 'Erode Corporation' not found — skipping corporation permissions.")
            return

        admin = StaffcreationOfficeDetails.objects.filter(
            username="erode.corp.admin", is_deleted=False
        ).first()
        supervisor = StaffcreationOfficeDetails.objects.filter(
            username="erode.corp.supervisor", is_deleted=False
        ).first()
        if not admin or not supervisor:
            self.log("Corporation staff not found — run CorporationAccessSeeder first. Skipping.")
            return

        actions = {
            name: UserScreenAction.objects.get_or_create(
                action_name=name,
                defaults={"variable_name": name, "is_active": True, "is_deleted": False},
            )[0]
            for name in ACTIONS
        }

        scope = {
            "state_id_id": corporation.state_id_id,
            "district_id_id": corporation.district_id_id,
            "area_type_id_id": corporation.area_type_id_id,
            "local_body_type": "corporation",
            "local_body_id": corporation.unique_id,
        }

        screens = list(
            UserScreen.objects.filter(
                is_deleted=False,
                is_active=True,
                mainscreen_id__is_deleted=False,
                mainscreen_id__is_active=True,
                mainscreen_id__mainscreentype_id__type_name="megamenu",
            )
            .select_related("mainscreen_id")
        )

        baseline_rows = admin_rows = supervisor_rows = 0
        for screen in screens:
            is_schedule_write = screen.userscreen_name in SCHEDULE_WRITE_SCREENS
            for action_name in ACTIONS:
                action = actions[action_name]

                # 1) super_admin baseline — the ceiling (full CRUD on everything)
                self._upsert(scope, "super_admin", None, screen, action)
                baseline_rows += 1

                # 2) admin staff — full CRUD everywhere
                self._upsert(scope, "staff", admin.staff_unique_id, screen, action)
                admin_rows += 1

                # 3) supervisor staff — CRUD on schedule screens, view elsewhere
                if is_schedule_write or action_name == "view":
                    self._upsert(scope, "staff", supervisor.staff_unique_id, screen, action)
                    supervisor_rows += 1

        self.log(
            f"---Corporation permissions seeded (baseline={baseline_rows}, "
            f"admin={admin_rows}, supervisor={supervisor_rows}) across {len(screens)} screens---"
        )

    def _upsert(self, scope, owner_kind, staff_id, screen, action):
        UserScreenPermission.objects.update_or_create(
            permission_owner_kind=owner_kind,
            staff_id=staff_id,
            mainscreen_id=screen.mainscreen_id,
            userscreen_id=screen,
            userscreenaction_id=action,
            is_deleted=False,
            **scope,
            defaults={
                "permission_type": "screen",
                "order_no": screen.order_no or 1,
                "is_active": True,
            },
        )
