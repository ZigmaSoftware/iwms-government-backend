from app.management.commands.seeders.base import BaseSeeder

from app.models.common_masters.state import State
from app.models.masters.city import City
from app.models.masters.district import District
from app.models.masters.ward import Ward
from app.models.masters.panchayat import Panchayat
from app.models.schedule_masters.collection_point import Collection_point
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class CollectionPointSeeder(BaseSeeder):
    name = "collection_point"

    def run(self):
        company = Company.objects.get(name="IWMS")
        project = Project.objects.get(name=f"{company.name} Main Project")

        tamil_nadu = State.objects.get(name="Tamil Nadu")
        chennai_dist = District.objects.get(name="Chennai")
        chennai_city = City.objects.get(name="Chennai City")

        # --- Ward-based CPs (1 per ward, 15 total) ---
        wards = list(
            Ward.objects.filter(
                company_id=company, project_id=project, is_deleted=False
            ).order_by("ward_name")
        )
        ward_created = 0
        for idx, ward in enumerate(wards, start=1):
            cp_name = f"CP-WARD-{idx:02d}"
            lat = float(ward.latitude) + 0.0005 if ward.latitude else 13.0840
            lon = float(ward.longitude) + 0.0005 if ward.longitude else 80.2720
            _, created = Collection_point.objects.update_or_create(
                cp_name=cp_name,
                ward_id=ward,
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": tamil_nadu,
                    "district_id": chennai_dist,
                    "city_id": chennai_city,
                    "panchayat_id": None,
                    "latitude": lat,
                    "longitude": lon,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                ward_created += 1

        # --- Panchayat-based CPs (1 per panchayat, 15 total) ---
        panchayats = list(
            Panchayat.objects.filter(
                company_id=company, project_id=project, is_deleted=False
            ).order_by("panchayat_name")
        )
        pan_created = 0
        for panchayat in panchayats:
            pan_num = "".join(filter(str.isdigit, panchayat.panchayat_name)) or "0"
            cp_name = f"CP-PAN{pan_num}-01"
            lat = float(panchayat.latitude) + 0.0005 if panchayat.latitude else 13.1500
            lon = float(panchayat.longitude) + 0.0005 if panchayat.longitude else 80.2000
            _, created = Collection_point.objects.update_or_create(
                cp_name=cp_name,
                panchayat_id=panchayat,
                company_id=company,
                project_id=project,
                defaults={
                    "state_id": tamil_nadu,
                    "district_id": chennai_dist,
                    "city_id": chennai_city,
                    "ward_id": None,
                    "latitude": lat,
                    "longitude": lon,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                pan_created += 1

        total = ward_created + pan_created
        self.log(
            f"---Collection Points seeded | ward CPs created={ward_created}/{len(wards)} "
            f"| panchayat CPs created={pan_created}/{len(panchayats)} | new total={total}---"
        )
