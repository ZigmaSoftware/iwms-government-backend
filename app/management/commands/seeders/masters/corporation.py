from app.management.commands.seeders import tn_local_bodies
from app.management.commands.seeders.masters.local_body import LocalBodySeeder
from app.models.masters.corporation import Corporation


class CorporationSeeder(LocalBodySeeder):
    name = "CorporationSeeder"
    model = Corporation
    name_field = "corporation_name"
    area_type_name = "Urban Local Body"
    label = "Corporations"

    def local_bodies(self):
        return tn_local_bodies.corporations()
