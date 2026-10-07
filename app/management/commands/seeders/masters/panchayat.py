from app.management.commands.seeders import tn_local_bodies
from app.management.commands.seeders.geo import coordinates
from app.management.commands.seeders.masters.local_body import LocalBodySeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.models.masters.panchayat import Panchayat


class PanchayatSeeder(LocalBodySeeder):
    """Every Tamil Nadu village panchayat, plus the demo panchayats the
    three operational districts' seed data is built on (tn_geo_data) —
    those keep their own point location unless a real village panchayat
    already has that name."""

    name = "PanchayatSeeder"
    model = Panchayat
    name_field = "panchayat_name"
    area_type_name = "Rural Local Body"
    label = "Panchayats"

    def local_bodies(self):
        panchayats = tn_local_bodies.panchayats()
        real = {(p["district"], p["name"]) for p in panchayats}
        return panchayats + [
            {"district": district_name, "name": name, "coordinates": coordinates((lat, lon))}
            for district_name, geo in DISTRICTS.items()
            for name, lat, lon, _pincode in geo["panchayats"]
            if (district_name, name) not in real
        ]
