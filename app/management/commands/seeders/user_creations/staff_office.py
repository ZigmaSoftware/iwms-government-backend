from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.models.masters.district import District
from app.models.masters.hierarchy_tree import HierarchyNode
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails
from app.utils.hierarchy import CITY_LEVEL_NAMES


def _district_node(district):
    """Resolve the hierarchy node mirrored from a District (geography is now a
    single location_node, not a district_id FK)."""
    if not district:
        return None
    return HierarchyNode.objects.filter(
        is_deleted=False,
        custom_properties__source_type="district",
        custom_properties__source_id=district.unique_id,
    ).first()


def _local_body_node(name):
    """Resolve a specific city/town/panchayat node by name (finer-grained
    than a district) - e.g. "Anthiyur Panchayat" mirrored by GeoToHierarchySeeder."""
    if not name:
        return None
    return HierarchyNode.objects.filter(
        is_deleted=False, name=name, level__name__in=CITY_LEVEL_NAMES,
    ).first()


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
            location_node = _local_body_node(local_body_name) or _district_node(district)

            defaults = {
                "employee_name": emp_name,
                "department_id": dept,
                "designation_id": desig,
                "location_node": location_node,
                "department": dept.department_name if dept else "",
                "designation": desig.designation_name if desig else "",
                "active_status": True,
                "login_enabled": True,
                "approval_status": StaffcreationOfficeDetails.APPROVAL_APPROVED,
                "is_active": True,
                "is_deleted": False,
            }

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
