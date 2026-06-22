from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District


class AreaTypeSeeder(BaseSeeder):
    name = "AreaTypeSeeder"

    # (district_name, area_type_name) — 5 records
    AREA_TYPE_ASSIGNMENTS = [
        ("Erode",      "Urban Local Body"),
        ("Salem",      "Urban Local Body"),
        ("Coimbatore", "Urban Local Body"),
        ("Chennai",    "Rural Local Body"),
        ("Madurai",    "Rural Local Body"),
    ]

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        if not tamil_nadu:
            self.log("Tamil Nadu state not found — run StateSeeder first.")
            return

        count = 0
        for district_name, area_type_name in self.AREA_TYPE_ASSIGNMENTS:
            district = District.objects.filter(state_id=tamil_nadu, name=district_name).first()
            if not district:
                self.log(f"District '{district_name}' not found — skipping.")
                continue

            AreaType.objects.update_or_create(
                state_id=tamil_nadu,
                district_id=district,
                name=area_type_name,
                defaults={"is_active": True, "is_deleted": False},
            )
            count += 1

        self.log(f"---Area types seeded ({count} records)---")
