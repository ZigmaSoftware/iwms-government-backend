from app.management.commands.seeders.base import BaseSeeder
from app.models.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat


class PanchayatSeeder(BaseSeeder):
    name = "PanchayatSeeder"

    PANCHAYATS = [
        "Anthiyur Panchayat",
        "Bhavani Panchayat",
        "Gobichettipalayam Panchayat",
        "Kavundampalayam Panchayat",
        "Modakkurichi Panchayat",
    ]

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        district = District.objects.filter(state_id=tamil_nadu, name="Erode").first()
        area_type = AreaType.objects.filter(
            state_id=tamil_nadu,
            district_id=district,
            name="Rural Local Body",
        ).first()

        if not tamil_nadu or not district or not area_type:
            self.log("Skipped: Tamil Nadu / Erode / Rural Local Body seed data not found.")
            return

        count = 0
        for panchayat_name in self.PANCHAYATS:
            _, created = Panchayat.objects.update_or_create(
                panchayat_name=panchayat_name,
                state_id=tamil_nadu,
                district_id=district,
                area_type_id=area_type,
                defaults={"is_active": True, "is_deleted": False},
            )
            action = "Created" if created else "Updated"
            self.log(f"{action}: {panchayat_name}")
            count += 1

        self.log(f"---Panchayats seeded ({count} records)---")
