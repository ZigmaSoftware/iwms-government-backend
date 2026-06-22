from django.contrib.auth.hashers import make_password

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.models.masters.district import District
from app.models.user_creations.staffcreation import StaffcreationOfficeDetails


class StaffOfficeSeeder(BaseSeeder):
    name = "StaffOfficeSeeder"

    # (employee_name, username, dept_code, designation_name, district_name)
    STAFF = [
        ("Ravi Kumar",      "ravi.kumar",      "TRP", "Vehicle Driver",          "Erode"),
        ("Priya Devi",      "priya.devi",      "FOP", "Waste Collector",         "Erode"),
        ("Muthu Samy",      "muthu.samy",      "FOP", "Field Supervisor",        "Salem"),
        ("Anbu Arasan",     "anbu.arasan",     "TRP", "Vehicle Driver",          "Salem"),
        ("Geetha Lakshmi",  "geetha.lakshmi",  "SAN", "Sanitation Inspector",    "Coimbatore"),
    ]

    def run(self):
        count = 0
        updated = 0
        for emp_name, username, dept_code, desig_name, district_name in self.STAFF:
            dept = Department.objects.filter(department_code=dept_code).first()
            desig = Designation.objects.filter(designation_name=desig_name).first()
            district = District.objects.filter(name=district_name).first()

            defaults = {
                "employee_name": emp_name,
                "department_id": dept,
                "designation_id": desig,
                "district_id": district,
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
                employee_name=emp_name,
                username=username,
                password=make_password("Staff@1234"),
                **defaults,
            )
            count += 1
            self.log(f"Created staff: {emp_name} ({username})")

        self.log(f"---Staff office records seeded ({count} created, {updated} updated)---")
