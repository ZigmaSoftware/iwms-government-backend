"""
CorporationAccessSeeder
=======================

Seeds a working corporation-scoped access demo for "Erode Corporation":

  - a Corporation Admin   (govt_corporation_admin)      — all modules CRUD
  - a Corporation Supervisor (govt_corporation_supervisor) — schedule/daily-trip CRUD

Both get a real ``StaffDataScope`` row scoped to Erode Corporation (no seeder
created StaffDataScope rows before). This is the demo the scoping work
(B1–B5) enforces: logging in as either user should show only Erode data.

Screen-level permissions for these two users are seeded separately by
``CorporationPermissionSeeder`` (screen-managements group, which runs after the
screen catalog exists).
"""

from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.corporation import Corporation
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.user_management.staff_data_scope import StaffDataScope
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails


# (username, employee_name, government role name)
CORPORATION_STAFF = [
    ("erode.corp.admin",      "Erode Corporation Admin",      "govt_corporation_admin"),
    ("erode.corp.supervisor", "Erode Corporation Supervisor", "govt_corporation_supervisor"),
]

DEFAULT_PASSWORD = "Staff@1234"


class CorporationAccessSeeder(BaseSeeder):
    name = "CorporationAccessSeeder"

    def run(self):
        corporation = Corporation.objects.filter(
            corporation_name="Erode Corporation", is_deleted=False
        ).first()
        if not corporation:
            self.log("Corporation 'Erode Corporation' not found — run CorporationSeeder first. Aborting.")
            return

        government_type = UserType.objects.filter(name__iexact="government").first()
        if not government_type:
            self.log("UserType 'government' not found — run UserTypeSeeder first. Aborting.")
            return

        created, updated = 0, 0
        for username, employee_name, role_name in CORPORATION_STAFF:
            role = GovernmentStaffUserType.objects.filter(
                name=role_name, is_deleted=False
            ).first()
            if not role:
                self.log(
                    f"GovernmentStaffUserType '{role_name}' not found — run "
                    "GovernmentStaffUserTypeSeeder first. Skipping."
                )
                continue

            defaults = {
                "employee_name": employee_name,
                "user_type_id": government_type,
                "governmentusertype_id": role,
                # Geo captured directly on the staff record (matches the finer
                # StaffDataScope below); inclusive-downward from the corporation.
                "state": corporation.state_id,
                "district": corporation.district_id,
                "area_type": corporation.area_type_id,
                "corporation": corporation,
                "active_status": True,
                "login_enabled": True,
                "is_active": True,
                "is_deleted": False,
            }

            staff = StaffcreationOfficeDetails.objects.filter(username=username).first()
            if staff:
                for field, value in defaults.items():
                    setattr(staff, field, value)
                staff.save(update_fields=[*defaults.keys(), "updated_at"])
                updated += 1
                self.log(f"Updated corporation staff: {employee_name} ({username})")
            else:
                staff = StaffcreationOfficeDetails.objects.create(
                    username=username,
                    password=make_password(DEFAULT_PASSWORD),
                    **defaults,
                )
                created += 1
                self.log(f"Created corporation staff: {employee_name} ({username})")

            # StaffDataScope scoped to Erode Corporation (state/district/
            # area_type/corporation) — the enforced access boundary.
            scope, _ = StaffDataScope.objects.update_or_create(
                staff=staff,
                is_deleted=False,
                defaults={
                    "state_id": corporation.state_id_id,
                    "district_id": corporation.district_id_id,
                    "area_type_id": corporation.area_type_id_id,
                    "is_active": True,
                },
            )
            scope.corporations.set([corporation.unique_id])
            scope.municipalities.clear()
            scope.town_panchayats.clear()
            scope.panchayat_unions.clear()
            scope.panchayats.clear()

        self.log(
            f"---Corporation access seeded ({created} created, {updated} updated); "
            f"login with password '{DEFAULT_PASSWORD}'---"
        )
