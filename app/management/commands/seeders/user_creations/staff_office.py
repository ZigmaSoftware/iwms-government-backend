from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.models.masters.district import District
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
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

    # (employee_name, username, dept_code, designation_name, district_name, local_body_name)
    # local_body_name is optional - most staff cover a whole district; a couple
    # are tagged to one specific town/panchayat inside it, so district- and
    # city-scoped assignment filtering both have real data to prove out.
    STAFF = [
        ("Ravi Kumar",      "ravi.kumar",      "TRP", "Vehicle Driver",          "Erode",      None),
        ("Priya Devi",      "priya.devi",      "FOP", "Waste Collector",         "Erode",      "Anthiyur Panchayat"),
        ("Muthu Samy",      "muthu.samy",      "FOP", "Field Supervisor",        "Salem",      None),
        ("Anbu Arasan",     "anbu.arasan",     "TRP", "Vehicle Driver",          "Salem",      None),
        ("Geetha Lakshmi",  "geetha.lakshmi",  "SAN", "Sanitation Inspector",    "Coimbatore", None),
    ]

    def run(self):
        count = 0
        updated = 0
        for emp_name, username, dept_code, desig_name, district_name, local_body_name in self.STAFF:
            dept = Department.objects.filter(department_code=dept_code).first()
            desig = Designation.objects.filter(designation_name=desig_name).first()
            district = District.objects.filter(name=district_name).first()
            local_body_field, local_body = _local_body(local_body_name)

            defaults = {
                "employee_name": emp_name,
                "department_id": dept,
                "designation_id": desig,
                "state": district.state_id if district else None,
                "district": district,
                "department": dept.department_name if dept else "",
                "designation": desig.designation_name if desig else "",
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
