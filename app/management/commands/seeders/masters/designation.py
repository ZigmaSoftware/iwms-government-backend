from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.department import Department
from app.models.masters.designation import Designation
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class DesignationSeeder(BaseSeeder):
    name = "designation"

    # (designation_name, department_code) — exactly 15 records
    # Includes all designations referenced by staff_office.py seeder
    DESIGNATIONS = [
        ("General Manager",        "MGMT"),
        ("HR Manager",             "HR"),
        ("Admin Manager",          "ADMIN"),
        ("Finance Manager",        "FIN"),
        ("Accounts Manager",       "ACC"),
        ("IT Manager",             "IT"),
        ("System Administrator",   "IT"),    # required by staff_office seeder
        ("Operations Manager",     "OPS"),
        ("Operations Supervisor",  "OPS"),   # required by staff_office seeder
        ("Operator",               "OPS"),   # required by staff_office seeder
        ("Transport Manager",      "TRANS"),
        ("Driver",                 "TRANS"), # required by staff_office seeder
        ("Field Supervisor",       "FIELD"),
        ("Customer Service Manager","CS"),
        ("Safety Officer",         "HS"),
    ]

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        dept_cache: dict[str, Department] = {}

        for designation_name, dept_code in self.DESIGNATIONS:
            if dept_code not in dept_cache:
                dept = Department.objects.filter(
                    company_id=company,
                    project_id=project,
                    department_code=dept_code,
                    is_deleted=False,
                ).first()
                if not dept:
                    self.log_error(f"Department '{dept_code}' not found — skipping {designation_name}")
                    continue
                dept_cache[dept_code] = dept

            department = dept_cache[dept_code]
            designation, created = Designation.objects.update_or_create(
                company_id=company,
                project_id=project,
                designation_name=designation_name,
                department_id=department,
                defaults={
                    "description": f"{designation_name} — {department.department_name}",
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            action = "Created" if created else "Updated"
            self.log(f"{designation.designation_name} [{dept_code}] ({action})")

        self.log(f"---Designations seeded ({len(self.DESIGNATIONS)} records)---")
