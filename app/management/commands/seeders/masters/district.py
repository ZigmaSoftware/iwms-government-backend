# seeders/masters/district.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class DistrictSeeder(BaseSeeder):
    name = "district"

    DISTRICTS = [
        "Chennai",
        "Coimbatore",
        "Madurai",
        "Tiruchirappalli",
        "Salem",
        "Tirunelveli",
        "Erode",
        "Vellore",
        "Thoothukudi",
        "Dindigul",
        "Thanjavur",
        "Ranipet",
        "Kancheepuram",
        "Chengalpattu",
        "Tiruvannamalai",
    ]

    def run(self):
        company, _ = Company.objects.get_or_create(
            name="IWMS",
            defaults={
                "description": "Integrated Waste Management System",
                "is_active": True,
                "is_deleted": False,
            },
        )
        project, _ = Project.objects.get_or_create(
            name=f"{company.name} Main Project",
            company_id=company,
            defaults={
                "description": f"Default project for {company.name}",
                "is_active": True,
                "is_deleted": False,
            },
        )

        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(name="Tamil Nadu")

        for name in self.DISTRICTS:
            District.objects.get_or_create(
                name=name,
                state_id=tamil_nadu,
                country_id=india,
                continent_id=asia,
                company_id=company,
                project_id=project,
            )

        self.log(f"---Districts seeded ({len(self.DISTRICTS)} records)---")
