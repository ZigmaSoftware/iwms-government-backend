from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.continent import Continent
from app.models.common_masters.country import Country
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.zone import Zone, GeoFencingType
from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


# 15 zones with varying lat/lon offsets from Chennai centre
ZONE_DATA = [
    ("Zone 1",  13.0827, 80.2707),
    ("Zone 2",  13.0900, 80.2800),
    ("Zone 3",  13.0750, 80.2600),
    ("Zone 4",  13.1000, 80.2900),
    ("Zone 5",  13.0680, 80.2550),
    ("Zone 6",  13.1100, 80.3000),
    ("Zone 7",  13.0600, 80.2450),
    ("Zone 8",  13.1200, 80.3100),
    ("Zone 9",  13.0520, 80.2350),
    ("Zone 10", 13.1300, 80.3200),
    ("Zone 11", 13.0440, 80.2250),
    ("Zone 12", 13.1400, 80.3300),
    ("Zone 13", 13.0360, 80.2150),
    ("Zone 14", 13.1500, 80.3400),
    ("Zone 15", 13.0280, 80.2050),
]


class ZoneSeeder(BaseSeeder):
    name = "zone"

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

        urban_area_type, _ = AreaType.objects.get_or_create(
            name="Urban",
            state_id=tamil_nadu,
            district_id=chennai_dist,
            city_id=chennai_city,
            defaults={
                "description": "Densely populated urban area",
                "is_active": True,
                "is_deleted": False,
            },
        )

        hierarchy, _ = AdministrativeHierarchy.objects.get_or_create(
            area_type=urban_area_type,
            level_name="Zone",
        )

        created_count = 0
        for zone_name, lat, lon in ZONE_DATA:
            _, created = Zone.objects.update_or_create(
                zone_name=zone_name,
                city_id=chennai_city,
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": tamil_nadu,
                    "district_id": chennai_dist,
                    "city_id": chennai_city,
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

        self.log(f"---Zones seeded ({len(ZONE_DATA)} records, {created_count} created)---")
