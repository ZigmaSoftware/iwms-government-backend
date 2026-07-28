from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.models.masters.department import Department
from app.models.masters.designation import Designation

# (department_code_prefix, designation_name, designation_group, description)
DESIGNATIONS = [
    ("SAN", "Sanitation Inspector",   "Supervisory", "Inspects sanitation and waste collection"),
    ("TRP", "Vehicle Driver",         "Operational", "Operates waste collection vehicles"),
    ("FOP", "Field Supervisor",       "Supervisory", "Supervises field collection teams"),
    ("FOP", "Waste Collector",        "Operational", "Collects waste from households"),
    ("ADM", "Administrative Officer", "Managerial",  "Handles administrative and HR duties"),
]


class DesignationSeeder(BaseSeeder):
    """Seeds the same 5 designations under every operational district's
    departments (SAN-ERD/TRP-ERD/... — see DepartmentSeeder)."""

    name = "DesignationSeeder"

    def run(self):
        count = 0
        for district_name, geo in DISTRICTS.items():
            district_code = geo["code"]
            for dept_code_prefix, desig_name, desig_group, description in DESIGNATIONS:
                dept = Department.objects.filter(
                    department_code=f"{dept_code_prefix}-{district_code}"
                ).first()
                if not dept:
                    self.log(f"Department '{dept_code_prefix}-{district_code}' not found — skipping.")
                    continue

                Designation.objects.update_or_create(
                    designation_name=desig_name,
                    department_id=dept,
                    defaults={
                        "designation_group": desig_group,
                        "description": description,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                count += 1

        self.log(f"---Designations seeded ({count} records)---")
