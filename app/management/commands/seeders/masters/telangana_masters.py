from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.district import District


class TelanganaMastersSeeder(BaseSeeder):
    """Seed Districts + AreaTypes + Corporations for Telangana.

    Mirrors the existing Tamil Nadu masters seeders (DistrictSeeder,
    AreaTypeSeeder, CorporationSeeder) exactly, but scoped to Telangana —
    those three are hardcoded to Tamil Nadu, so Telangana (which already
    exists as a State, with a StateLeaderLogin, but had zero districts)
    needed its own equivalent before any trip data could be generated.
    """

    name = "telangana_masters"

    # (name, code, lat, lon)
    DISTRICTS = [
        ("Hyderabad", "HYD", 17.3850, 78.4867),
        ("Warangal", "WGL", 17.9689, 79.5941),
        ("Nizamabad", "NZB", 18.6725, 78.0941),
        ("Karimnagar", "KRN", 18.4386, 79.1288),
        ("Khammam", "KHM", 17.2473, 80.1514),
    ]

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        telangana = State.objects.filter(name="Telangana", country_id=india, continent_id=asia).first()
        if not telangana:
            self.log("Telangana state not found — run StateSeeder first.")
            return

        district_count = 0
        area_type_count = 0
        corporation_count = 0

        for name, code, lat, lon in self.DISTRICTS:
            district, _ = District.objects.update_or_create(
                state_id=telangana,
                name=name,
                defaults={
                    "continent_id": asia,
                    "country_id": india,
                    "district_code": code,
                    "coordinates": coordinates((lat, lon), (lat + 0.03, lon - 0.03), (lat - 0.03, lon + 0.03)),
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            district_count += 1

            urban, _ = AreaType.objects.update_or_create(
                state_id=telangana,
                district_id=district,
                name="Urban Local Body",
                defaults={
                    "coordinates": coordinates((lat, lon), (lat + 0.02, lon - 0.02)),
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            AreaType.objects.update_or_create(
                state_id=telangana,
                district_id=district,
                name="Rural Local Body",
                defaults={
                    "coordinates": coordinates((lat - 0.05, lon - 0.05), (lat + 0.05, lon + 0.05)),
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            area_type_count += 2

            Corporation.objects.update_or_create(
                state_id=telangana,
                district_id=district,
                area_type_id=urban,
                corporation_name=f"{name} Corporation",
                defaults={
                    "coordinates": coordinates((lat, lon), (lat + 0.02, lon - 0.02)),
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            corporation_count += 1

        self.log(
            "---Telangana masters seeded | "
            f"Districts: {district_count} | Area types: {area_type_count} | "
            f"Corporations: {corporation_count}---"
        )
