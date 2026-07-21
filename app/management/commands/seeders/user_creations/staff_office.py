from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.department import Department
from app.models.masters.district import District
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.userType import UserType
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails

_LOCAL_BODY_MODELS = [
    ("corporation", Corporation, "corporation_name"),
    ("municipality", Municipality, "municipality_name"),
    ("town_panchayat", TownPanchayat, "town_panchayat_name"),
    ("panchayat_union", PanchayatUnion, "union_name"),
    ("panchayat", Panchayat, "panchayat_name"),
]


def _local_body(name):
    """Resolve a specific corporation/municipality/.../panchayat record by
    name (finer-grained than a district). Returns (field_name, instance) or
    (None, None) if no local body with that name exists."""
    if not name:
        return None, None
    for field_name, model, name_field in _LOCAL_BODY_MODELS:
        obj = model.objects.filter(is_deleted=False, **{name_field: name}).first()
        if obj:
            return field_name, obj
    return None, None


class StaffOfficeSeeder(BaseSeeder):
    name = "StaffOfficeSeeder"

    # (employee_name, username, dept_code, designation, district_name, local_body_name, govt_role)
    # `designation` is free text (not an FK master) — government designations
    # vary too widely across states/districts to enumerate.
    # `govt_role` is a GovernmentStaffUserType name: this is a government-only
    # project, so every seeded staff is a government user (no staff/contractor).
    # local_body_name is optional - most staff cover a whole district; a couple
    # are tagged to one specific town/panchayat inside it, so district- and
    # city-scoped assignment filtering both have real data to prove out.
    STAFF = [
        ("Ravi Kumar",      "ravi.kumar",      "TRP", "Vehicle Driver",       "Erode",      None,                 "govt_district_driver"),
        ("Priya Devi",      "priya.devi",      "FOP", "Waste Collector",      "Erode",      "Anthiyur Panchayat", "govt_district_operator"),
        ("Muthu Samy",      "muthu.samy",      "FOP", "Field Supervisor",     "Salem",      None,                 "govt_district_officer"),
        ("Anbu Arasan",     "anbu.arasan",     "TRP", "Vehicle Driver",       "Salem",      None,                 "govt_district_driver"),
        ("Geetha Lakshmi",  "geetha.lakshmi",  "SAN", "Sanitation Inspector", "Coimbatore", None,                 "govt_district_inspector"),
    ]

    def run(self):
        government_type = UserType.objects.filter(name__iexact="government").first()
        if not government_type:
            self.log("UserType 'government' not found — run UserTypeSeeder first. Skipping.")
            return

        count = 0
        updated = 0
        for emp_name, username, dept_code, designation, district_name, local_body_name, govt_role in self.STAFF:
            dept = Department.objects.filter(department_code=dept_code).first()
            district = District.objects.filter(name=district_name).first()
            local_body_field, local_body = _local_body(local_body_name)
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
                "employee_name": emp_name,
                "department_id": dept,
                "state": district.state_id if district else None,
                "district": district,
                "department": dept.department_name if dept else "",
                # Free-text designation (no FK). Explicitly clear the legacy
                # designation_id FK so re-seeding normalizes older rows too.
                "designation": designation,
                "designation_id": None,
                # Government-only project: every staff is a government user.
                "user_type_id": government_type,
                "governmentusertype_id": role,
                "staffusertype_id": None,
                "contractorusertype_id": None,
                "active_status": True,
                "login_enabled": True,
                "is_active": True,
                "is_deleted": False,
            }
            if local_body_field:
                defaults[local_body_field] = local_body

            staff = StaffcreationOfficeDetails.objects.filter(username=username).first()
            if staff:
                for field, value in defaults.items():
                    setattr(staff, field, value)
                staff.save(update_fields=[*defaults.keys(), "updated_at"])
                updated += 1
                self.log(f"Updated staff: {emp_name} ({username})")
                continue

            StaffcreationOfficeDetails.objects.create(
                username=username,
                password=make_password("Staff@1234"),
                **defaults,
            )
            count += 1
            self.log(f"Created staff: {emp_name} ({username})")

        self.log(f"---Staff office records seeded ({count} created, {updated} updated)---")
