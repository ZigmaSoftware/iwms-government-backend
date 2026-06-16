from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.city import City
from app.models.masters.panchayat import Panchayat, GeoFencingType
from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


PANCHAYAT_DATA = [
    {"name": "Panchayat 1",  "agreed_weight_kg": 500.00, "latitude": 13.150000, "longitude": 80.200000},
    {"name": "Panchayat 2",  "agreed_weight_kg": 750.00, "latitude": 13.160000, "longitude": 80.210000},
    {"name": "Panchayat 3",  "agreed_weight_kg": 600.00, "latitude": 13.170000, "longitude": 80.220000},
    {"name": "Panchayat 4",  "agreed_weight_kg": 450.00, "latitude": 13.180000, "longitude": 80.230000},
    {"name": "Panchayat 5",  "agreed_weight_kg": 820.00, "latitude": 13.190000, "longitude": 80.240000},
    {"name": "Panchayat 6",  "agreed_weight_kg": 530.00, "latitude": 13.200000, "longitude": 80.250000},
    {"name": "Panchayat 7",  "agreed_weight_kg": 670.00, "latitude": 13.210000, "longitude": 80.260000},
    {"name": "Panchayat 8",  "agreed_weight_kg": 490.00, "latitude": 13.220000, "longitude": 80.270000},
    {"name": "Panchayat 9",  "agreed_weight_kg": 710.00, "latitude": 13.230000, "longitude": 80.280000},
    {"name": "Panchayat 10", "agreed_weight_kg": 580.00, "latitude": 13.240000, "longitude": 80.290000},
    {"name": "Panchayat 11", "agreed_weight_kg": 640.00, "latitude": 13.250000, "longitude": 80.300000},
    {"name": "Panchayat 12", "agreed_weight_kg": 760.00, "latitude": 13.260000, "longitude": 80.310000},
    {"name": "Panchayat 13", "agreed_weight_kg": 520.00, "latitude": 13.270000, "longitude": 80.320000},
    {"name": "Panchayat 14", "agreed_weight_kg": 880.00, "latitude": 13.280000, "longitude": 80.330000},
    {"name": "Panchayat 15", "agreed_weight_kg": 430.00, "latitude": 13.290000, "longitude": 80.340000},
]


class PanchayatSeeder(BaseSeeder):
    name = "panchayat"

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        rural_area_type = AreaType.objects.get(name="Rural")

        hierarchy = AdministrativeHierarchy.objects.get(
            area_type=rural_area_type,
            level_name="Panchayat",
        )

        for entry in PANCHAYAT_DATA:
            panchayat, created = Panchayat.objects.update_or_create(
                panchayat_name=entry["name"],
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": tamil_nadu,
                    "district_id": chennai_dist,
                    "city_id": chennai_city,
                    "area_type_id": rural_area_type,
                    "hierarchy_id": hierarchy,
                    "geofencing_type": GeoFencingType.POLYGON,
                    "agreed_weight_kg": entry["agreed_weight_kg"],
                    "weight_unit": "kg",
                    "effective_from": None,
                    "latitude": entry["latitude"],
                    "longitude": entry["longitude"],
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            action = "Created" if created else "Updated"
            self.log(f"Panchayat seeded: {panchayat.panchayat_name} | agreed={entry['agreed_weight_kg']} kg ({action})")

        self.log(f"---Panchayats seeded ({len(PANCHAYAT_DATA)} records)---")
