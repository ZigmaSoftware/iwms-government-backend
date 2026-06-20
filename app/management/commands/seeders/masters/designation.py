from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.department import Department
from app.models.masters.designation import Designation


class DesignationSeeder(BaseSeeder):
    name = "DesignationSeeder"

    # (department_code, designation_name, designation_group, description)
    DESIGNATIONS = [
        ("SAN", "Sanitation Inspector",   "Supervisory",  "Inspects sanitation and waste collection"),
        ("TRP", "Vehicle Driver",         "Operational",  "Operates waste collection vehicles"),
        ("FOP", "Field Supervisor",       "Supervisory",  "Supervises field collection teams"),
        ("FOP", "Waste Collector",        "Operational",  "Collects waste from households"),
        ("ADM", "Administrative Officer", "Managerial",   "Handles administrative and HR duties"),
    ]

    def run(self):
        dept_cache = {}
        count = 0
        for dept_code, desig_name, desig_group, description in self.DESIGNATIONS:
            if dept_code not in dept_cache:
                dept = Department.objects.filter(department_code=dept_code).first()
                if not dept:
                    self.log(f"Department '{dept_code}' not found — skipping.")
                    continue
                dept_cache[dept_code] = dept

            dept = dept_cache[dept_code]
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
