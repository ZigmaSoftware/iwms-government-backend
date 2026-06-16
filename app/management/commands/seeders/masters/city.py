# seeders/masters/city.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class CitySeeder(BaseSeeder):
    name = "city"

    # (city_name, district_name)
    CITIES = [
        ("Chennai City",         "Chennai"),
        ("Coimbatore City",      "Coimbatore"),
        ("Madurai City",         "Madurai"),
        ("Tiruchirappalli City", "Tiruchirappalli"),
        ("Salem City",           "Salem"),
        ("Tirunelveli City",     "Tirunelveli"),
        ("Erode City",           "Erode"),
        ("Vellore City",         "Vellore"),
        ("Thoothukudi City",     "Thoothukudi"),
        ("Dindigul City",        "Dindigul"),
        ("Thanjavur City",       "Thanjavur"),
        ("Ranipet City",         "Ranipet"),
        ("Kancheepuram City",    "Kancheepuram"),
        ("Chengalpattu City",    "Chengalpattu"),
        ("Tiruvannamalai City",  "Tiruvannamalai"),
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
        district_cache = {}

        for city_name, district_name in self.CITIES:
            if district_name not in district_cache:
                district_cache[district_name] = District.objects.get(
                    name=district_name, state_id=tamil_nadu
                )
            City.objects.get_or_create(
                name=city_name,
                continent_id=asia,
                country_id=india,
                state_id=tamil_nadu,
                district_id=district_cache[district_name],
                company_id=company,
                project_id=project,
            )

        self.log(f"---Cities seeded ({len(self.CITIES)} records)---")
