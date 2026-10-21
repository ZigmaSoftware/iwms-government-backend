from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType, AreaTypeName
from app.models.masters.district import District


class AreaTypeSeeder(BaseSeeder):
    """An Urban and a Rural Local Body area type for every Tamil Nadu
    district; both span the whole district, so they carry its boundary."""

    name = "AreaTypeSeeder"

    AREA_TYPE_NAMES = (AreaTypeName.URBAN_LOCAL_BODY.value, AreaTypeName.RURAL_LOCAL_BODY.value)

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        if not tamil_nadu:
            self.log("Tamil Nadu state not found — run StateSeeder first.")
            return

        districts = District.objects.filter(state_id=tamil_nadu.unique_id, is_deleted=False)
        rows = [
            {
                "state_id": tamil_nadu.unique_id,
                "district_id": district.unique_id,
                "name": area_type_name,
                "coordinates": district.coordinates,
                "is_active": True,
                "is_deleted": False,
            }
            for district in districts
            for area_type_name in self.AREA_TYPE_NAMES
        ]
        created, updated = self.bulk_upsert(
            AreaType, rows, key_fields=("district_id", "name"), scope={"state_id": tamil_nadu.unique_id}
        )
        self.log(f"---Area types seeded ({len(rows)} records: {created} created, {updated} updated)---")
