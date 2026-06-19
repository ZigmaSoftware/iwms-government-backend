from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District


class AreaTypeSeeder(BaseSeeder):
    name = "AreaTypeSeeder"
    AREA_TYPES = ["Urban Local Body", "Rural Local Body"]

    def run(self):
        tamil_nadu = State.objects.get(name="Tamil Nadu")
        districts = District.objects.filter(state_id=tamil_nadu, name__in=["Erode", "Salem", "Coimbatore", "Chennai", "Madurai"])

        count = 0
        for district in districts:
            for area_type_name in self.AREA_TYPES:
                AreaType.objects.update_or_create(
                    state_id=tamil_nadu,
                    district_id=district,
                    name=area_type_name,
                    defaults={"is_active": True, "is_deleted": False},
                )
                count += 1

        self.log(f"Area types seeded ({count} district-scoped records).")
