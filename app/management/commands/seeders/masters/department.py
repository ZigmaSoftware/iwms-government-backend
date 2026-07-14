from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.corporation import Corporation
from app.models.masters.department import Department


class DepartmentSeeder(BaseSeeder):
    name = "DepartmentSeeder"

    # Departments now belong to a Corporation (corporation-level government
    # product). The demo focuses on Erode Corporation, so departments are
    # seeded under it; the corporation-scoped department filter then has data.
    CORPORATION_NAME = "Erode Corporation"

    # (department_name, department_code, description)
    DEPARTMENTS = [
        ("Sanitation",      "SAN", "Waste management and sanitation operations"),
        ("Transport",       "TRP", "Vehicle operations and fleet management"),
        ("Field Operations","FOP", "Field collection and on-ground monitoring"),
        ("Administration",  "ADM", "Administrative operations"),
    ]

    def run(self):
        corporation = Corporation.objects.filter(
            corporation_name=self.CORPORATION_NAME, is_deleted=False
        ).first()
        if not corporation:
            self.log(
                f"Corporation '{self.CORPORATION_NAME}' not found — "
                "seeding departments without a corporation."
            )

        for dept_name, dept_code, description in self.DEPARTMENTS:
            Department.objects.update_or_create(
                department_code=dept_code,
                defaults={
                    "department_name": dept_name,
                    "description": description,
                    "corporation_id": corporation,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        self.log(f"---Departments seeded ({len(self.DEPARTMENTS)} records)---")
