from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


class BluePlanetSeeder(BaseSeeder):
    name = "blue_planet"

    ATTENDANCE_API_URL = "http://zigfly.in/attendance-api/api/sync/recognized"
    ATTENDANCE_API_KEY = "ZIGFLY_SYNC_2025"
    GPS_API_URL = "https://api.vamosys.com/getVehicleHistory"
    WEIGHMENT_API_URL = (
        "https://zigma.in/d2d/folders/waste_collected_summary_report/"
        "waste_collected_data_api.php"
    )

    def run(self):
        company, company_created = Company.objects.update_or_create(
            name="Blue Planet",
            defaults={
                "description": "Blue Planet waste management operations",
                "is_active": True,
                "is_deleted": False,
            },
        )

        project_defaults = {
            "Noida BP": {
                "description": "Blue Planet Noida operations",
                "gps_api_url": self.GPS_API_URL,
                "weighment_api_url": self.WEIGHMENT_API_URL,
                "attendance_api_url": self.ATTENDANCE_API_URL,
                "attendance_api_key": self.ATTENDANCE_API_KEY,
                "is_active": True,
                "is_deleted": False,
            },
            "Palakkad BP": {
                "description": "Blue Planet Palakkad operations",
                "is_active": True,
                "is_deleted": False,
            },
        }

        created = 0
        updated = 0
        for name, defaults in project_defaults.items():
            _, was_created = Project.objects.update_or_create(
                company_id=company,
                name=name,
                defaults=defaults,
            )
            created += int(was_created)
            updated += int(not was_created)

        company_action = "Created" if company_created else "Updated"
        self.log(
            f"{company_action} Blue Planet | Projects created: {created}, updated: {updated}"
        )
