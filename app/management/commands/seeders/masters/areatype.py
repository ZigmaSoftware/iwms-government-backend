from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.areatype import AreaType
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class AreaTypeSeeder(BaseSeeder):
    name = "areatype"

    # (name, description)
    AREA_TYPES = [
        ("Urban",                "Densely populated urban area"),
        ("Rural",                "Sparsely populated rural area"),
        ("Semi-Urban",           "Transitional semi-urban area"),
        ("Industrial",           "Industrial and manufacturing zone"),
        ("Commercial",           "Commercial business district"),
        ("Residential Zone",     "Planned residential zone"),
        ("Agricultural",         "Agricultural and farming land"),
        ("Coastal",              "Coastal and shoreline area"),
        ("Hill Station",         "Hilly terrain and hill station"),
        ("Tribal",               "Tribal and scheduled area"),
        ("Special Economic Zone","Government-designated SEZ"),
        ("Heritage Zone",        "Historical and heritage district"),
        ("Educational Zone",     "Campus and educational district"),
        ("Healthcare Zone",      "Hospital and healthcare cluster"),
        ("Mixed Use",            "Mixed residential and commercial"),
    ]

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        for name, description in self.AREA_TYPES:
            _, created = AreaType.objects.update_or_create(
                name=name,
                defaults={
                    "state_id": tamil_nadu,
                    "district_id": chennai_dist,
                    "city_id": chennai_city,
                    "company_id": company,
                    "project_id": project,
                    "description": description,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            action = "Created" if created else "Updated"
            self.log(f"AreaType seeded: {name} ({action})")

        self.log(f"---AreaTypes seeded ({len(self.AREA_TYPES)} records)---")
