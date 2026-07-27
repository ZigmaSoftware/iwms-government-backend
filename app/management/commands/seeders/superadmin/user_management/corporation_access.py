"""
CorporationAccessSeeder
=======================

Seeds a working corporation-scoped access demo for each of the three
operational districts' Corporations (Erode/Coimbatore/Salem):

  - a Corporation Admin   (govt_corporation_admin)      — all modules CRUD
  - a Corporation Supervisor (govt_corporation_supervisor) — schedule/daily-trip CRUD

Each gets a real ``StaffDataScope`` row scoped to its own Corporation. This
is the demo the scoping work (B1–B5) enforces: logging in as any of these
six users should show only that corporation's data.

Screen-level permissions for these users are seeded separately by
``CorporationPermissionSeeder`` (screen-managements group, which runs after the
screen catalog exists).
"""

from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.models.masters.corporation import Corporation
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.user_management.staff_data_scope import StaffDataScope
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails

DEFAULT_PASSWORD = "Staff@1234"


class CorporationAccessSeeder(BaseSeeder):
    name = "CorporationAccessSeeder"

    def run(self):
        government_type = UserType.objects.filter(name__iexact="government").first()
        if not government_type:
            self.log("UserType 'government' not found — run UserTypeSeeder first. Aborting.")
            return

        created, updated = 0, 0
        for district_name, geo in DISTRICTS.items():
            corporation = Corporation.objects.filter(
                corporation_name=geo["corporation_name"], is_deleted=False
            ).first()
            if not corporation:
                self.log(f"Corporation '{geo['corporation_name']}' not found — skipping.")
                continue

            code = geo["code"].lower()
            corp_staff = [
                (f"{code}.corp.admin", f"{district_name} Corporation Admin", "govt_corporation_admin"),
                (f"{code}.corp.supervisor", f"{district_name} Corporation Supervisor", "govt_corporation_supervisor"),
            ]

            for username, employee_name, role_name in corp_staff:
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

                # StaffDataScope scoped to this Corporation (state/district/
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
