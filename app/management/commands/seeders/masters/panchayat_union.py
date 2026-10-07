from app.management.commands.seeders import tn_local_bodies
from app.management.commands.seeders.geo import coordinates
from app.management.commands.seeders.masters.local_body import LocalBodySeeder
from app.management.commands.seeders.tn_geo_data import DEMO_ONLY_PANCHAYAT_UNIONS
from app.models.masters.panchayat_union import PanchayatUnion


class PanchayatUnionSeeder(LocalBodySeeder):
    """Every Tamil Nadu panchayat union (LGD block panchayat), plus the
    demo-only unions the operational seed data uses (tn_geo_data)."""

    name = "PanchayatUnionSeeder"
    model = PanchayatUnion
    name_field = "union_name"
    area_type_name = "Rural Local Body"
    label = "Panchayat unions"

    def local_bodies(self):
        unions = tn_local_bodies.panchayat_unions()
        real = {(u["district"], u["name"]) for u in unions}
        return unions + [
            {"district": district, "name": name, "coordinates": coordinates((lat, lon))}
            for district, name, lat, lon in DEMO_ONLY_PANCHAYAT_UNIONS
            if (district, name) not in real
        ]
