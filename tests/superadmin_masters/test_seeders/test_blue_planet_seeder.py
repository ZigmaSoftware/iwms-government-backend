import pytest

from app.management.commands.seeders.superadmin_masters.blue_planet import (
    BluePlanetSeeder,
)
from app.management.commands.seeders.superadmin_masters.project import ProjectSeeder
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project


@pytest.mark.django_db
class TestBluePlanetSeeder:
    def test_creates_company_and_two_projects_with_noida_api_configuration(self):
        BluePlanetSeeder().run()

        company = Company.objects.get(name="Blue Planet")
        projects = Project.objects.filter(company_id=company).order_by("name")

        assert list(projects.values_list("name", flat=True)) == [
            "Noida BP",
            "Palakkad BP",
        ]

        noida = projects.get(name="Noida BP")
        assert noida.attendance_api_url == BluePlanetSeeder.ATTENDANCE_API_URL
        assert noida.attendance_api_key == BluePlanetSeeder.ATTENDANCE_API_KEY
        assert noida.gps_api_url == BluePlanetSeeder.GPS_API_URL
        assert noida.weighment_api_url == BluePlanetSeeder.WEIGHMENT_API_URL

    def test_is_idempotent_and_generic_project_seeder_does_not_add_third_project(self):
        BluePlanetSeeder().run()
        BluePlanetSeeder().run()
        ProjectSeeder().run()

        company = Company.objects.get(name="Blue Planet")
        assert Project.objects.filter(company_id=company).count() == 2
