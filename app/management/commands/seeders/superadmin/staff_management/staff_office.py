from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS, TAMIL_NAME_POOL
from app.models.masters.department import Department
from app.models.masters.district import District
from app.models.masters.corporation import Corporation
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails

# Drivers/operators must be numerous enough that DRIVERS_PER_DISTRICT *
# OPERATORS_PER_DISTRICT unique (driver, operator) combinations comfortably
# exceed the largest district's total ward count x 2 (every local body's
# StaffTemplate pool needs one unique pairing per ward per collection type,
# and pairs are never reused anywhere in the district — see
# StaffTemplateSeeder / ward_utils.py), plus 1 corporation-scoped field
# supervisor and 1 sanitation inspector.
DRIVERS_PER_DISTRICT = 9
OPERATORS_PER_DISTRICT = 9

# (department_code_prefix, designation, govt_role_suffix, is_corp_scoped)
ROLE_PLAN = (
    [("TRP", "Vehicle Driver", "govt_district_driver", False)] * DRIVERS_PER_DISTRICT
    + [("FOP", "Waste Collector", "govt_district_operator", False)] * OPERATORS_PER_DISTRICT
    + [
        ("FOP", "Field Supervisor", "govt_district_officer", True),
        ("SAN", "Sanitation Inspector", "govt_district_inspector", True),
    ]
)


class StaffOfficeSeeder(BaseSeeder):
    """Government staff per operational district (Erode/Coimbatore/Salem):
    8 drivers + 8 operators (sized so StaffTemplateSeeder can form one
    unique driver/operator pairing per ward-level trip plan without ever
    reusing a pairing), plus 1 field supervisor + 1 sanitation inspector.
    Usernames carry a district-code suffix (e.g. `ravi.kumar.erd`) so the
    same first/last name pattern reused across 3 districts never collides
    on StaffcreationOfficeDetails.username (globally unique)."""

    name = "StaffOfficeSeeder"

    def run(self):
        government_type = UserType.objects.filter(name__iexact="government").first()
        if not government_type:
            self.log("UserType 'government' not found — run UserTypeSeeder first. Skipping.")
            return

        count = 0
        updated = 0
        for district_idx, (district_name, geo) in enumerate(DISTRICTS.items()):
            district = District.objects.filter(name=district_name).first()
            if not district:
                self.log(f"District '{district_name}' not found — skipping staff.")
                continue
            corporation = Corporation.objects.filter(
                corporation_name=geo["corporation_name"], is_deleted=False
            ).first()
            code = geo["code"]

            for slot, (dept_prefix, designation, govt_role, is_corp_scoped) in enumerate(ROLE_PLAN):
                name_idx = district_idx * len(ROLE_PLAN) + slot
                full_name = TAMIL_NAME_POOL[name_idx % len(TAMIL_NAME_POOL)]
                first, _, last = full_name.partition(" ")
                username = f"{first.lower()}.{last.lower().replace(' ', '')}.{code.lower()}"

                dept = Department.objects.filter(department_code=f"{dept_prefix}-{code}").first()
                role = GovernmentStaffUserType.objects.filter(
                    name=govt_role, is_deleted=False
                ).first()
                if not role:
                    self.log(
                        f"GovernmentStaffUserType '{govt_role}' not found — run "
                        "GovernmentStaffUserTypeSeeder first. Skipping this staff."
                    )
                    continue

                defaults = {
                    "employee_name": full_name,
                    "department_id": dept,
                    "state": district.state_id,
                    "district": district,
                    # Supervisor/inspector additionally scoped to the corporation
                    # itself so corporation-level schedule filtering has data.
                    "corporation": corporation if is_corp_scoped else None,
                    "department": dept.department_name if dept else "",
                    "designation": designation,
                    "designation_id": None,
                    "user_type_id": government_type,
                    "governmentusertype_id": role,
                    "staffusertype_id": None,
                    "contractorusertype_id": None,
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
                    self.log(f"Updated staff: {full_name} ({username})")
                else:
                    StaffcreationOfficeDetails.objects.create(
                        username=username,
                        password=make_password("Staff@1234"),
                        **defaults,
                    )
                    count += 1
                    self.log(f"Created staff: {full_name} ({username})")

        self.log(f"---Staff office records seeded ({count} created, {updated} updated)---")
