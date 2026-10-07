from app.management.commands.seeders import tn_local_bodies
from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.common_masters.continent import Continent
from app.models.superadmin.common_masters.country import Country
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District


class DistrictSeeder(BaseSeeder):
    """All 38 Tamil Nadu districts with their real boundary polygons
    (seeders/tn_local_bodies.py)."""

    name = "DistrictSeeder"

    def run(self):
        asia = Continent.objects.get(name="Asia")
        india = Country.objects.get(name="India")
        tamil_nadu = State.objects.get(
            name="Tamil Nadu", country_id=india.unique_id, continent_id=asia.unique_id
        )

        rows = [
            {
                "state_id": tamil_nadu.unique_id,
                "name": district["name"],
                "continent_id": asia.unique_id,
                "country_id": india.unique_id,
                "district_code": district["code"],
                "coordinates": district["coordinates"],
                "is_active": True,
                "is_deleted": False,
            }
            for district in tn_local_bodies.districts()
        ]
        created, updated = self.bulk_upsert(
            District, rows, key_fields=("state_id", "name"), scope={"state_id": tamil_nadu.unique_id}
        )
        self.log(f"Districts seeded ({len(rows)} Tamil Nadu records: {created} created, {updated} updated).")
