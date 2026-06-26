from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.models.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat


class PanchayatSeeder(BaseSeeder):
    name = "PanchayatSeeder"

    PANCHAYATS = [
        ("Anthiyur Panchayat", coordinates((11.5750, 77.5900), (11.5660, 77.6040))),
        ("Bhavani Panchayat", coordinates((11.4437, 77.6845), (11.4550, 77.6720))),
        ("Gobichettipalayam Panchayat", coordinates((11.4524, 77.4355), (11.4620, 77.4480))),
        ("Kavundampalayam Panchayat", coordinates((11.2932, 77.6011), (11.3010, 77.6150))),
        ("Modakkurichi Panchayat", coordinates((11.3805, 77.7032), (11.3910, 77.7160))),
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

        PanchayatUnion.objects.update_or_create(
            state_id=tamil_nadu,
            district_id=district,
            area_type_id=area_type,
            union_name="Erode Panchayat Union",
            defaults={"is_active": True, "is_deleted": False},
        )
        panchayat, created = Panchayat.objects.update_or_create(
            panchayat_name="Sample Panchayat",
            state_id=tamil_nadu,
            district_id=district,
            area_type_id=area_type,
            defaults={
                "is_active": True,
                "is_deleted": False,
            },
        )
        action = "Created" if created else "Updated"
        self.log(f"{action}: {panchayat.panchayat_name}.")
