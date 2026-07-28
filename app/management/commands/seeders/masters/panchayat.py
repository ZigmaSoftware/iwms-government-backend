from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.geo import coordinates
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat


class PanchayatSeeder(BaseSeeder):
    """Rural panchayats for the three fully-built-out operational districts
    (Erode/Coimbatore/Salem) — real district-appropriate panchayat/town
    names, sourced from tn_geo_data.DISTRICTS."""

    name = "PanchayatSeeder"

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        if not tamil_nadu:
            self.log("Tamil Nadu state not found — run StateSeeder first.")
            return

        count = 0
        for district_name, geo in DISTRICTS.items():
            district = District.objects.filter(state_id=tamil_nadu, name=district_name).first()
            area_type = AreaType.objects.filter(
                state_id=tamil_nadu,
                district_id=district,
                name="Rural Local Body",
            ).first()
            if not district or not area_type:
                self.log(f"Rural area type for '{district_name}' not found — skipping.")
                continue

            for panchayat_name, lat, lon, _pincode in geo["panchayats"]:
                Panchayat.objects.update_or_create(
                    panchayat_name=panchayat_name,
                    state_id=tamil_nadu,
                    district_id=district,
                    area_type_id=area_type,
                    defaults={
                        "coordinates": coordinates((lat, lon)),
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                count += 1

        self.log(f"---Panchayats seeded ({count} records)---")
