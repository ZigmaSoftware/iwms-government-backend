from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward, GeoFencingType
from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


# 15 wards, all under Zone 1, with slight lat/lon variations
WARD_DATA = [
    ("Ward 1",  13.0840, 80.2720),
    ("Ward 2",  13.0855, 80.2735),
    ("Ward 3",  13.0870, 80.2750),
    ("Ward 4",  13.0885, 80.2765),
    ("Ward 5",  13.0900, 80.2780),
    ("Ward 6",  13.0915, 80.2795),
    ("Ward 7",  13.0930, 80.2810),
    ("Ward 8",  13.0945, 80.2825),
    ("Ward 9",  13.0960, 80.2840),
    ("Ward 10", 13.0975, 80.2855),
    ("Ward 11", 13.0990, 80.2870),
    ("Ward 12", 13.1005, 80.2885),
    ("Ward 13", 13.1020, 80.2900),
    ("Ward 14", 13.1035, 80.2915),
    ("Ward 15", 13.1050, 80.2930),
]


class WardSeeder(BaseSeeder):
    name = "ward"

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
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        zone_1 = Zone.objects.get(
            zone_name="Zone 1",
            city_id=chennai_city,
            company_id=company,
            project_id=project,
        )

        urban_area_type = AreaType.objects.get(
            name="Urban",
            state_id=tamil_nadu,
            district_id=chennai_dist,
            city_id=chennai_city,
        )

        hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(
            area_type=urban_area_type,
            level_name="Ward",
        )

        created_count = 0
        for ward_name, lat, lon in WARD_DATA:
            _, created = Ward.objects.update_or_create(
                ward_name=ward_name,
                zone_id=zone_1,
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": tamil_nadu,
                    "district_id": chennai_dist,
                    "city_id": chennai_city,
                    "zone_id": zone_1,
                    "area_type_id": urban_area_type,
                    "hierarchy_id": hierarchy,
                    "latitude": lat,
                    "longitude": lon,
                    "geofencing_type": GeoFencingType.POLYGON,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                created_count += 1

        self.log(f"---Wards seeded ({len(WARD_DATA)} records, {created_count} created)---")
