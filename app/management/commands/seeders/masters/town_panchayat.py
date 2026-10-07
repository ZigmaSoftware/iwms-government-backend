from app.management.commands.seeders import tn_local_bodies
from app.management.commands.seeders.masters.local_body import LocalBodySeeder
from app.models.masters.town_panchayat import TownPanchayat


class TownPanchayatSeeder(LocalBodySeeder):
    name = "TownPanchayatSeeder"
    model = TownPanchayat
    name_field = "town_panchayat_name"
    area_type_name = "Urban Local Body"
    label = "Town panchayats"

    def local_bodies(self):
        return tn_local_bodies.town_panchayats()
