from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.models.masters.corporation import Corporation
from app.models.masters.department import Department

# (department_name, department_code_prefix, description)
DEPARTMENTS = [
    ("Sanitation",       "SAN", "Waste management and sanitation operations"),
    ("Transport",        "TRP", "Vehicle operations and fleet management"),
    ("Field Operations", "FOP", "Field collection and on-ground monitoring"),
    ("Administration",   "ADM", "Administrative operations"),
]


class DepartmentSeeder(BaseSeeder):
    """Seeds the same 4 departments under every operational district's
    Corporation. department_code is globally unique, so each district gets
    its own suffixed code (e.g. SAN-ERD, SAN-CBE, SAN-SLM)."""

    name = "DepartmentSeeder"

    def run(self):
        count = 0
        for district_name, geo in DISTRICTS.items():
            corporation = Corporation.objects.filter(
                corporation_name=geo["corporation_name"], is_deleted=False
            ).first()
            if not corporation:
                self.log(f"Corporation '{geo['corporation_name']}' not found — skipping.")
                continue

            district_code = geo["code"]
            for dept_name, dept_code_prefix, description in DEPARTMENTS:
                Department.objects.update_or_create(
                    department_code=f"{dept_code_prefix}-{district_code}",
                    defaults={
                        "department_name": dept_name,
                        "description": description,
                        "corporation_id": corporation,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                count += 1

        self.log(f"---Departments seeded ({count} records)---")
