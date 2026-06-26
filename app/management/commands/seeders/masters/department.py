from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.department import Department


class DepartmentSeeder(BaseSeeder):
    name = "DepartmentSeeder"

    # (department_name, department_code, description)
    DEPARTMENTS = [
        ("Sanitation",      "SAN", "Waste management and sanitation operations"),
        ("Transport",       "TRP", "Vehicle operations and fleet management"),
        ("Field Operations","FOP", "Field collection and on-ground monitoring"),
        ("Administration",  "ADM", "Administrative and HR operations"),
        ("IT & Systems",    "ITS", "Technology, systems and digital operations"),
    ]

    def run(self):
        for dept_name, dept_code, description in self.DEPARTMENTS:
            Department.objects.update_or_create(
                department_code=dept_code,
                defaults={
                    "department_name": dept_name,
                    "description": description,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        self.log(f"---Departments seeded ({len(self.DEPARTMENTS)} records)---")
